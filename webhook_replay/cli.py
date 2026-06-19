import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import questionary
import typer
from dateutil import parser as date_parser
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .archive import WebhookArchiver
from .models import ArchiveFilter, WebhookRequest, WebhookStatus
from .replay import WebhookReplayer
from .signature import HmacAlgorithm, SignatureGenerator, SignatureVerifier
from .storage import Storage, StorageType
from .summary_renderers import SummaryFormat, SummaryGenerator

app = typer.Typer(
    name="webhook-replay",
    help="Webhook 回放 CLI - 归档、重放和管理 Webhook 请求",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _create_storage(
    storage_type: StorageType = StorageType.JSON,
    storage_path: Optional[Path] = None,
) -> Storage:
    return Storage(storage_type, storage_path)


def _print_request_table(requests: List[WebhookRequest], show_details: bool = False) -> None:
    if not requests:
        console.print("[yellow]没有找到匹配的请求[/yellow]")
        return

    table = Table(title="Webhook 请求列表", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("状态", style="magenta")
    table.add_column("URL", style="green")
    table.add_column("方法", style="yellow")
    table.add_column("时间", style="blue")

    if show_details:
        table.add_column("签名头", style="dim")

    for req in requests:
        status_style = {
            WebhookStatus.SUCCESS: "green",
            WebhookStatus.FAILED: "red",
            WebhookStatus.PENDING: "yellow",
            WebhookStatus.ARCHIVED: "blue",
        }.get(req.status, "white")

        status_display = f"[{status_style}]{req.status.value}[/{status_style}]"
        row = [
            req.id[:12] + "...",
            status_display,
            str(req.url),
            req.method,
            req.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        if show_details:
            row.append(req.signature_header)
        table.add_row(*row)

    console.print(table)
    console.print(f"共 {len(requests)} 条记录")


def _interactive_select_requests(requests: List[WebhookRequest]) -> List[WebhookRequest]:
    if not requests:
        return []

    choices = [
        questionary.Choice(
            title=f"[{req.status.value}] {req.url} - {req.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            value=req,
            checked=False,
        )
        for req in requests
    ]

    choices.insert(0, questionary.Choice(title="全选", value="select_all", checked=False))
    choices.insert(1, questionary.Choice(title="取消全选", value="deselect_all", checked=False))

    selected = questionary.checkbox(
        "请选择要重放的请求（空格键选择，回车键确认）：",
        choices=choices,
        instruction=" 按 a 全选，按 i 反选",
    ).ask()

    if selected is None:
        return []

    if "select_all" in selected:
        return requests
    if "deselect_all" in selected:
        return []

    return [req for req in selected if isinstance(req, WebhookRequest)]


_storage_option = typer.Option(
    StorageType.JSON,
    "--storage",
    "-S",
    help="存储后端类型",
)

_storage_path_option = typer.Option(
    None,
    "--storage-path",
    help="存储路径（JSON: 目录路径，SQLite: 数据库文件路径）",
)


@app.command("archive")
def archive(
    url: str = typer.Option(..., "--url", "-u", help="Webhook 目标 URL"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="请求体内容"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="从 JSON 文件读取请求体"),
    header: Optional[List[str]] = typer.Option(None, "--header", "-H", help="请求头，格式: Key:Value"),
    method: str = typer.Option("POST", "--method", "-X", help="HTTP 方法"),
    signature_header: str = typer.Option(
        "X-Webhook-Signature", "--sig-header", help="签名头名称"
    ),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """归档 Webhook 请求"""
    storage = _create_storage(storage_type, storage_path)
    archiver = WebhookArchiver(storage)

    if file:
        if not file.exists():
            console.print(f"[red]文件不存在: {file}[/red]")
            raise typer.Exit(code=1)
        request = archiver.archive_from_json_file(file, url, signature_header)
    elif body:
        headers = {}
        if header:
            for h in header:
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()
        request = archiver.archive(url, body, headers, method, signature_header)
    else:
        console.print("[red]必须提供 --body 或 --file 参数[/red]")
        raise typer.Exit(code=1)

    console.print(Panel.fit(
        f"[green]请求已归档[/green]\n"
        f"ID: {request.id}\n"
        f"URL: {request.url}\n"
        f"存储: {storage_type.value}"
    ))


@app.command("list")
def list_requests(
    status: Optional[WebhookStatus] = typer.Option(None, "--status", "-s", help="按状态筛选"),
    start_date: Optional[str] = typer.Option(None, "--start", help="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end", help="结束日期 (YYYY-MM-DD)"),
    url_pattern: Optional[str] = typer.Option(None, "--url", help="URL 匹配模式"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="限制数量"),
    details: bool = typer.Option(False, "--details", "-d", help="显示详细信息"),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """列出已归档的请求"""
    try:
        start_dt = date_parser.parse(start_date) if start_date else None
        end_dt = date_parser.parse(end_date) if end_date else None
    except ValueError as e:
        console.print(f"[red]日期格式错误: {e}[/red]")
        raise typer.Exit(code=1)

    filter = ArchiveFilter(
        status=status,
        start_date=start_dt,
        end_date=end_dt,
        url_pattern=url_pattern,
        limit=limit,
    )

    storage = _create_storage(storage_type, storage_path)
    requests = storage.list_requests(filter)
    _print_request_table(requests, details)


@app.command("replay")
def replay(
    request_id: Optional[str] = typer.Option(None, "--id", help="要重放的请求 ID"),
    all_failed: bool = typer.Option(False, "--all-failed", help="重放所有失败的请求"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="交互式选择失败请求进行重放"
    ),
    secret: Optional[str] = typer.Option(None, "--secret", help="签名密钥，用于重新签名"),
    resign: bool = typer.Option(False, "--resign", help="重新计算签名"),
    algorithm: HmacAlgorithm = typer.Option(
        HmacAlgorithm.SHA256,
        "--algorithm",
        "-a",
        help="HMAC 签名算法",
    ),
    delay: int = typer.Option(0, "--delay", help="请求间隔（毫秒）"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="限制重放数量"),
    output_format: SummaryFormat = typer.Option(
        SummaryFormat.TEXT,
        "--output-format",
        "-o",
        help="输出格式",
    ),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """重放 Webhook 请求"""
    storage = _create_storage(storage_type, storage_path)
    replayer = WebhookReplayer(storage, secret=secret, signature_algorithm=algorithm)
    requests_to_replay: List[WebhookRequest] = []

    if request_id:
        req = storage.get_request(request_id)
        if not req:
            console.print(f"[red]未找到请求 ID: {request_id}[/red]")
            raise typer.Exit(code=1)
        requests_to_replay = [req]
    elif interactive:
        filter = ArchiveFilter(status=WebhookStatus.FAILED)
        failed_requests = storage.list_requests(filter)
        if not failed_requests:
            console.print("[green]没有失败的请求需要重放[/green]")
            raise typer.Exit(code=0)
        requests_to_replay = _interactive_select_requests(failed_requests)
        if not requests_to_replay:
            console.print("[yellow]未选择任何请求[/yellow]")
            raise typer.Exit(code=0)
    elif all_failed:
        filter = ArchiveFilter(status=WebhookStatus.FAILED, limit=limit)
        requests_to_replay = storage.list_requests(filter)
    else:
        console.print("[red]必须指定 --id、--all-failed 或 --interactive[/red]")
        raise typer.Exit(code=1)

    if not requests_to_replay:
        console.print("[yellow]没有需要重放的请求[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"[cyan]准备重放 {len(requests_to_replay)} 个请求...[/cyan]")
    if resign and secret:
        console.print(f"[cyan]使用算法 {algorithm.value} 重新签名[/cyan]")

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("重放中...", total=len(requests_to_replay))

        def callback(current, total):
            progress.update(task, advance=1, description=f"重放中... ({current}/{total})")

        results = replayer.batch_replay(
            requests_to_replay,
            resign=resign,
            delay_ms=delay,
            progress_callback=callback,
        )

    summary_gen = SummaryGenerator(storage)
    summary = summary_gen.generate_summary(results)
    output = summary_gen.render_summary(summary, output_format)

    if output_format == SummaryFormat.JSON:
        console.print(output)
    elif output_format == SummaryFormat.MARKDOWN:
        console.print(output)
    else:
        console.print(Panel.fit(output, title="重放结果摘要"))


@app.command("verify")
def verify_signature(
    body: str = typer.Option(..., "--body", "-b", help="请求体内容"),
    signature: str = typer.Option(..., "--signature", "-s", help="签名值"),
    secret: str = typer.Option(..., "--secret", help="签名密钥"),
    algorithm: HmacAlgorithm = typer.Option(
        HmacAlgorithm.SHA256, "--algorithm", "-a", help="HMAC 算法"
    ),
    max_age: int = typer.Option(300, "--max-age", help="最大允许时间差（秒）"),
):
    """验证 Webhook 签名"""
    verifier = SignatureVerifier()
    valid = verifier.verify(body, signature, secret, algorithm=algorithm, max_age=max_age)

    if valid:
        console.print(f"[green]✓ 签名验证通过 (算法: {algorithm.value})[/green]")
    else:
        console.print(f"[red]✗ 签名验证失败 (算法: {algorithm.value})[/red]")
        raise typer.Exit(code=1)


@app.command("sign")
def generate_signature(
    body: str = typer.Option(..., "--body", "-b", help="请求体内容"),
    secret: str = typer.Option(..., "--secret", help="签名密钥"),
    algorithm: HmacAlgorithm = typer.Option(
        HmacAlgorithm.SHA256, "--algorithm", "-a", help="HMAC 算法"
    ),
    include_timestamp: bool = typer.Option(
        True, "--timestamp/--no-timestamp", help="是否包含时间戳"
    ),
    raw: bool = typer.Option(False, "--raw", help="只输出原始签名（不含时间戳前缀格式）"),
):
    """生成 Webhook 签名"""
    generator = SignatureGenerator(secret, algorithm)

    if raw:
        signature = generator.generate_raw(body)
        console.print(f"[green]原始签名 ({algorithm.value}):[/green] {signature}")
    else:
        header_value = generator.generate_header_value(body, include_timestamp=include_timestamp)
        console.print(f"[green]签名头值 ({algorithm.value}):[/green] {header_value}")


@app.command("delete")
def delete_request(
    request_id: str = typer.Argument(..., help="要删除的请求 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="不提示确认"),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """删除指定的请求"""
    storage = _create_storage(storage_type, storage_path)

    if not force:
        confirm = typer.confirm(f"确定要删除请求 {request_id} 吗？")
        if not confirm:
            console.print("[yellow]已取消删除[/yellow]")
            raise typer.Exit(code=0)

    if storage.delete_request(request_id):
        console.print(f"[green]请求 {request_id} 已删除[/green]")
    else:
        console.print(f"[red]未找到请求 {request_id}[/red]")
        raise typer.Exit(code=1)


@app.command("clear")
def clear_all(
    force: bool = typer.Option(False, "--force", "-f", help="不提示确认"),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """清除所有请求记录"""
    storage = _create_storage(storage_type, storage_path)
    count = storage.count()
    if count == 0:
        console.print("[yellow]没有可清除的记录[/yellow]")
        raise typer.Exit(code=0)

    if not force:
        confirm = typer.confirm(
            f"确定要清除所有 {count} 条记录吗？此操作不可恢复！"
        )
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit(code=0)

    deleted = storage.clear_all()
    console.print(f"[green]已清除 {deleted} 条记录 (存储: {storage_type.value})[/green]")


@app.command("stats")
def show_stats(
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """显示存储统计信息"""
    storage = _create_storage(storage_type, storage_path)
    summary_gen = SummaryGenerator(storage)
    stats = summary_gen.get_storage_stats()

    table = Table(title=f"存储统计 ({storage_type.value})")
    table.add_column("状态", style="cyan")
    table.add_column("数量", style="magenta", justify="right")

    for status, count in stats.items():
        style = {
            "success": "green",
            "failed": "red",
            "pending": "yellow",
            "archived": "blue",
        }.get(status, "white")
        table.add_row(f"[{style}]{status}[/{style}]", str(count))

    console.print(table)


@app.command("export")
def export_requests(
    output_file: Path = typer.Argument(..., help="输出文件路径"),
    status: Optional[WebhookStatus] = typer.Option(None, "--status", "-s", help="按状态筛选"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="限制数量"),
    storage_type: StorageType = _storage_option,
    storage_path: Optional[Path] = _storage_path_option,
):
    """导出请求为 JSON 文件"""
    filter = ArchiveFilter(status=status, limit=limit)
    storage = _create_storage(storage_type, storage_path)
    requests = storage.list_requests(filter)

    data = [req.model_dump(mode="json") for req in requests]
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    console.print(f"[green]已导出 {len(requests)} 条记录到 {output_file}[/green]")


def main():
    app()


if __name__ == "__main__":
    main()
