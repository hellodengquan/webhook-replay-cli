import time
from typing import Callable, Dict, List, Optional

import requests

from .models import ReplayResult, WebhookRequest, WebhookStatus
from .signature import SignatureGenerator
from .storage import Storage


class WebhookReplayer:
    def __init__(
        self,
        storage: Optional[Storage] = None,
        secret: Optional[str] = None,
        signature_algorithm: str = "sha256",
        timeout: int = 30,
        verify_ssl: bool = True,
    ):
        self.storage = storage or Storage()
        self.secret = secret
        self.signature_algorithm = signature_algorithm
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session = requests.Session()

    def _prepare_headers(self, request: WebhookRequest, resign: bool) -> Dict[str, str]:
        headers = request.headers.copy()

        if resign and self.secret:
            generator = SignatureGenerator(self.secret, self.signature_algorithm)
            new_signature = generator.generate_header_value(request.body)
            headers[request.signature_header] = new_signature

        return headers

    def replay(self, request: WebhookRequest, resign: bool = False) -> ReplayResult:
        start_time = time.time()
        headers = self._prepare_headers(request, resign)

        new_signature = None
        if resign and self.secret:
            generator = SignatureGenerator(self.secret, self.signature_algorithm)
            new_signature, _ = generator.generate(request.body)

        try:
            response = self._session.request(
                method=request.method,
                url=str(request.url),
                headers=headers,
                data=request.body,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

            duration = (time.time() - start_time) * 1000
            success = 200 <= response.status_code < 300

            result = ReplayResult(
                request_id=request.id,
                success=success,
                status_code=response.status_code,
                response_body=response.text[:2000],
                duration_ms=round(duration, 2),
                new_signature=new_signature,
                retried=True,
            )

            new_status = WebhookStatus.SUCCESS if success else WebhookStatus.FAILED
            self.storage.update_status(request.id, new_status)

            return result

        except requests.RequestException as e:
            duration = (time.time() - start_time) * 1000
            self.storage.update_status(request.id, WebhookStatus.FAILED)

            return ReplayResult(
                request_id=request.id,
                success=False,
                error_message=str(e),
                duration_ms=round(duration, 2),
                new_signature=new_signature,
                retried=True,
            )

    def batch_replay(
        self,
        requests: List[WebhookRequest],
        resign: bool = False,
        delay_ms: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[ReplayResult]:
        results = []
        total = len(requests)

        for i, request in enumerate(requests, 1):
            result = self.replay(request, resign)
            results.append(result)

            if progress_callback:
                progress_callback(i, total)

            if delay_ms > 0 and i < total:
                time.sleep(delay_ms / 1000)

        return results

    def replay_by_id(self, request_id: str, resign: bool = False) -> Optional[ReplayResult]:
        request = self.storage.get_request(request_id)
        if not request:
            return None
        return self.replay(request, resign)

    def replay_failed(
        self,
        resign: bool = False,
        limit: Optional[int] = None,
        delay_ms: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[ReplayResult]:
        from .models import ArchiveFilter

        filter = ArchiveFilter(status=WebhookStatus.FAILED, limit=limit)
        failed_requests = self.storage.list_requests(filter)
        return self.batch_replay(failed_requests, resign, delay_ms, progress_callback)
