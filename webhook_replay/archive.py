import json
from pathlib import Path
from typing import Dict, Optional

from .models import WebhookRequest, WebhookStatus
from .storage import Storage


class WebhookArchiver:
    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()

    def archive(
        self,
        url: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
        method: str = "POST",
        signature_header: str = "X-Webhook-Signature",
    ) -> WebhookRequest:
        headers = headers or {}
        original_signature = headers.get(signature_header)

        request = WebhookRequest(
            url=url,
            method=method.upper(),
            headers=headers,
            body=body,
            original_signature=original_signature,
            signature_header=signature_header,
            status=WebhookStatus.ARCHIVED,
        )

        self.storage.save_request(request)
        return request

    def archive_from_json_file(
        self, file_path: Path, url: str, signature_header: str = "X-Webhook-Signature"
    ) -> WebhookRequest:
        with open(file_path, "r") as f:
            content = f.read()

        return self.archive(
            url=url,
            body=content,
            signature_header=signature_header,
        )

    def archive_from_dict(
        self,
        data: Dict,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        signature_header: str = "X-Webhook-Signature",
    ) -> WebhookRequest:
        body = json.dumps(data, ensure_ascii=False)
        return self.archive(
            url=url,
            body=body,
            headers=headers,
            signature_header=signature_header,
        )

    def batch_archive(
        self,
        requests_data: list[Dict],
        signature_header: str = "X-Webhook-Signature",
    ) -> list[WebhookRequest]:
        archived = []
        for req_data in requests_data:
            request = self.archive(
                url=req_data["url"],
                body=req_data.get("body", ""),
                headers=req_data.get("headers", {}),
                method=req_data.get("method", "POST"),
                signature_header=signature_header,
            )
            archived.append(request)
        return archived
