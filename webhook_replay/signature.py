import hashlib
import hmac
import time
from contextlib import suppress
from enum import Enum
from typing import Optional, Tuple


class HmacAlgorithm(str, Enum):
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"

    @classmethod
    def from_string(cls, value: str) -> "HmacAlgorithm":
        normalized = value.lower().replace("-", "")
        mapping = {
            "sha1": cls.SHA1,
            "hmacsha1": cls.SHA1,
            "sha256": cls.SHA256,
            "hmacsha256": cls.SHA256,
            "sha512": cls.SHA512,
            "hmacsha512": cls.SHA512,
        }
        if normalized not in mapping:
            raise ValueError(f"Unsupported algorithm: {value}. Supported: {[a.value for a in cls]}")
        return mapping[normalized]


SUPPORTED_ALGORITHMS = {
    HmacAlgorithm.SHA1: hashlib.sha1,
    HmacAlgorithm.SHA256: hashlib.sha256,
    HmacAlgorithm.SHA512: hashlib.sha512,
}


class SignatureGenerator:
    def __init__(
        self,
        secret: str,
        algorithm: HmacAlgorithm | str = HmacAlgorithm.SHA256,
    ):
        self.secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        if isinstance(algorithm, str):
            self.algorithm = HmacAlgorithm.from_string(algorithm)
        else:
            self.algorithm = algorithm
        self._hash_func = SUPPORTED_ALGORITHMS[self.algorithm]

    def generate(self, body: str, timestamp: Optional[int] = None) -> Tuple[str, int]:
        timestamp = timestamp or int(time.time())
        payload = f"{timestamp}.{body}"
        signature = hmac.new(
            self.secret,
            payload.encode("utf-8"),
            self._hash_func,
        ).hexdigest()
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

    def generate_raw(self, body: str) -> str:
        signature = hmac.new(
            self.secret,
            body.encode("utf-8"),
            self._hash_func,
        ).hexdigest()
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
                with suppress(ValueError, IndexError):
                    timestamp = int(part[2:])
            elif part.startswith("sig="):
                signature = part[4:]

        return timestamp, signature

    def verify(
        self,
        body: str,
        header_value: str,
        secret: str,
        algorithm: HmacAlgorithm | str = HmacAlgorithm.SHA256,
        max_age: int = 300,
    ) -> bool:
        timestamp, signature = self.parse_header(header_value)
        if not signature:
            signature = header_value

        generator = SignatureGenerator(secret, algorithm)

        if timestamp is not None:
            return generator.verify(body, signature, timestamp, max_age)
        else:
            expected_signature = generator.generate_raw(body)
            return hmac.compare_digest(expected_signature, signature)
