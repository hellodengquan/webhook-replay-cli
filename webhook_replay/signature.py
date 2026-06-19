import hashlib
import hmac
import time
from typing import Optional, Tuple


class SignatureGenerator:
    def __init__(self, secret: str, algorithm: str = "sha256"):
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self.algorithm = algorithm

    def generate(self, body: str, timestamp: Optional[int] = None) -> Tuple[str, int]:
        timestamp = timestamp or int(time.time())
        payload = f"{timestamp}.{body}"
        signature = hmac.new(self.secret, payload.encode("utf-8"), self.algorithm).hexdigest()
        return signature, timestamp

    def verify(self, body: str, signature: str, timestamp: int, max_age: int = 300) -> bool:
        if max_age and abs(time.time() - timestamp) > max_age:
            return False

        expected_signature, _ = self.generate(body, timestamp)
        return hmac.compare_digest(expected_signature, signature)

    def generate_header_value(self, body: str, include_timestamp: bool = True) -> str:
        signature, timestamp = self.generate(body)
        if include_timestamp:
            return f"t={timestamp},sig={signature}"
        return signature


class SignatureVerifier:
    @staticmethod
    def parse_header(header_value: str) -> Tuple[Optional[int], str]:
        timestamp = None
        signature = ""

        parts = header_value.split(",")
        for part in parts:
            part = part.strip()
            if part.startswith("t="):
                try:
                    timestamp = int(part[2:])
                except (ValueError, IndexError):
                    pass
            elif part.startswith("sig="):
                signature = part[4:]

        return timestamp, signature

    def verify(
        self,
        body: str,
        header_value: str,
        secret: str,
        algorithm: str = "sha256",
        max_age: int = 300,
    ) -> bool:
        timestamp, signature = self.parse_header(header_value)
        if not signature:
            signature = header_value

        generator = SignatureGenerator(secret, algorithm)

        if timestamp is not None:
            return generator.verify(body, signature, timestamp, max_age)
        else:
            expected_signature = hmac.new(
                secret.encode("utf-8") if isinstance(secret, str) else secret,
                body.encode("utf-8"),
                algorithm,
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
