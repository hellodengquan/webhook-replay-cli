import hashlib
import hmac

import pytest

from webhook_replay.signature import (
    HmacAlgorithm,
    SignatureGenerator,
    SignatureVerifier,
    SUPPORTED_ALGORITHMS,
)


class TestHmacAlgorithmEnum:
    def test_sha1_value(self):
        assert HmacAlgorithm.SHA1.value == "sha1"

    def test_sha512_value(self):
        assert HmacAlgorithm.SHA512.value == "sha512"

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("sha1", HmacAlgorithm.SHA1),
            ("SHA1", HmacAlgorithm.SHA1),
            ("hmac-sha1", HmacAlgorithm.SHA1),
            ("HMAC-SHA1", HmacAlgorithm.SHA1),
            ("hmacsha1", HmacAlgorithm.SHA1),
            ("sha512", HmacAlgorithm.SHA512),
            ("SHA512", HmacAlgorithm.SHA512),
            ("hmac-sha512", HmacAlgorithm.SHA512),
            ("HMAC-SHA512", HmacAlgorithm.SHA512),
            ("hmacsha512", HmacAlgorithm.SHA512),
        ],
    )
    def test_from_string(self, input_str: str, expected: HmacAlgorithm):
        assert HmacAlgorithm.from_string(input_str) == expected

    def test_from_string_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            HmacAlgorithm.from_string("md5")


class TestSupportedAlgorithmsMapping:
    def test_sha1_maps_to_hashlib_sha1(self):
        assert SUPPORTED_ALGORITHMS[HmacAlgorithm.SHA1] is hashlib.sha1

    def test_sha512_maps_to_hashlib_sha512(self):
        assert SUPPORTED_ALGORITHMS[HmacAlgorithm.SHA512] is hashlib.sha512


class TestSignatureGeneratorSha1:
    @pytest.fixture
    def gen_sha1(self) -> SignatureGenerator:
        return SignatureGenerator("test-secret", HmacAlgorithm.SHA1)

    def test_generate_returns_signature_and_timestamp(self, gen_sha1: SignatureGenerator):
        sig, ts = gen_sha1.generate("body content")
        assert isinstance(sig, str)
        assert isinstance(ts, int)
        assert len(sig) == 40  # SHA-1 hex digest length

    def test_generate_deterministic(self, gen_sha1: SignatureGenerator):
        sig1, ts = gen_sha1.generate("body", timestamp=1700000000)
        sig2, _ = gen_sha1.generate("body", timestamp=1700000000)
        assert sig1 == sig2

    def test_generate_raw_sha1(self, gen_sha1: SignatureGenerator):
        raw = gen_sha1.generate_raw("test body")
        expected = hmac.new(
            b"test-secret",
            b"test body",
            hashlib.sha1,
        ).hexdigest()
        assert raw == expected
        assert len(raw) == 40

    def test_generate_raw_differs_from_sha256(self):
        gen1 = SignatureGenerator("key", HmacAlgorithm.SHA1)
        gen2 = SignatureGenerator("key", HmacAlgorithm.SHA256)
        raw1 = gen1.generate_raw("body")
        raw2 = gen2.generate_raw("body")
        assert raw1 != raw2
        assert len(raw1) == 40
        assert len(raw2) == 64

    def test_generate_header_value_with_timestamp(self, gen_sha1: SignatureGenerator):
        header = gen_sha1.generate_header_value("body", include_timestamp=True)
        assert header.startswith("t=")
        assert ",sig=" in header
        parts = header.split(",")
        assert len(parts) == 2

    def test_generate_header_value_without_timestamp(self, gen_sha1: SignatureGenerator):
        header = gen_sha1.generate_header_value("body", include_timestamp=False)
        assert "t=" not in header
        assert len(header) == 40

    def test_verify_valid_signature(self, gen_sha1: SignatureGenerator):
        sig, ts = gen_sha1.generate("body", timestamp=1700000000)
        assert gen_sha1.verify("body", sig, 1700000000, max_age=0) is True

    def test_verify_wrong_body(self, gen_sha1: SignatureGenerator):
        sig, ts = gen_sha1.generate("body", timestamp=1700000000)
        assert gen_sha1.verify("wrong", sig, 1700000000, max_age=0) is False


class TestSignatureGeneratorSha512:
    @pytest.fixture
    def gen_sha512(self) -> SignatureGenerator:
        return SignatureGenerator("test-secret", HmacAlgorithm.SHA512)

    def test_generate_returns_signature_and_timestamp(self, gen_sha512: SignatureGenerator):
        sig, ts = gen_sha512.generate("body content")
        assert isinstance(sig, str)
        assert isinstance(ts, int)
        assert len(sig) == 128  # SHA-512 hex digest length

    def test_generate_raw_sha512(self, gen_sha512: SignatureGenerator):
        raw = gen_sha512.generate_raw("test body")
        expected = hmac.new(
            b"test-secret",
            b"test body",
            hashlib.sha512,
        ).hexdigest()
        assert raw == expected
        assert len(raw) == 128

    def test_generate_raw_differs_from_sha256(self):
        gen512 = SignatureGenerator("key", HmacAlgorithm.SHA512)
        gen256 = SignatureGenerator("key", HmacAlgorithm.SHA256)
        raw512 = gen512.generate_raw("body")
        raw256 = gen256.generate_raw("body")
        assert raw512 != raw256
        assert len(raw512) == 128
        assert len(raw256) == 64

    def test_generate_deterministic(self, gen_sha512: SignatureGenerator):
        sig1, _ = gen_sha512.generate("body", timestamp=1700000000)
        sig2, _ = gen_sha512.generate("body", timestamp=1700000000)
        assert sig1 == sig2

    def test_generate_header_value_with_timestamp(self, gen_sha512: SignatureGenerator):
        header = gen_sha512.generate_header_value("body", include_timestamp=True)
        assert header.startswith("t=")
        assert ",sig=" in header

    def test_generate_header_value_without_timestamp(self, gen_sha512: SignatureGenerator):
        header = gen_sha512.generate_header_value("body", include_timestamp=False)
        assert "t=" not in header
        assert len(header) == 128

    def test_verify_valid_signature(self, gen_sha512: SignatureGenerator):
        sig, ts = gen_sha512.generate("body", timestamp=1700000000)
        assert gen_sha512.verify("body", sig, 1700000000, max_age=0) is True

    def test_verify_wrong_body(self, gen_sha512: SignatureGenerator):
        sig, ts = gen_sha512.generate("body", timestamp=1700000000)
        assert gen_sha512.verify("wrong", sig, 1700000000, max_age=0) is False


class TestSignatureVerifierSha1:
    @pytest.fixture
    def verifier(self) -> SignatureVerifier:
        return SignatureVerifier()

    def test_verify_sha1_header(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA1)
        header = gen.generate_header_value("body")
        assert verifier.verify("body", header, "secret", algorithm=HmacAlgorithm.SHA1) is True

    def test_verify_sha1_wrong_secret(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA1)
        header = gen.generate_header_value("body")
        assert verifier.verify("body", header, "wrong", algorithm=HmacAlgorithm.SHA1) is False

    def test_verify_sha1_raw_signature(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA1)
        raw_sig = gen.generate_raw("body")
        assert verifier.verify("body", raw_sig, "secret", algorithm=HmacAlgorithm.SHA1, max_age=0) is True


class TestSignatureVerifierSha512:
    @pytest.fixture
    def verifier(self) -> SignatureVerifier:
        return SignatureVerifier()

    def test_verify_sha512_header(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA512)
        header = gen.generate_header_value("body")
        assert verifier.verify("body", header, "secret", algorithm=HmacAlgorithm.SHA512) is True

    def test_verify_sha512_wrong_secret(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA512)
        header = gen.generate_header_value("body")
        assert verifier.verify("body", header, "wrong", algorithm=HmacAlgorithm.SHA512) is False

    def test_verify_sha512_raw_signature(self, verifier: SignatureVerifier):
        gen = SignatureGenerator("secret", HmacAlgorithm.SHA512)
        raw_sig = gen.generate_raw("body")
        assert verifier.verify("body", raw_sig, "secret", algorithm=HmacAlgorithm.SHA512, max_age=0) is True


class TestCrossAlgorithmIsolation:
    def test_sha1_sig_fails_sha256_verify(self):
        gen1 = SignatureGenerator("key", HmacAlgorithm.SHA1)
        gen2 = SignatureGenerator("key", HmacAlgorithm.SHA256)
        header1 = gen1.generate_header_value("body")
        verifier = SignatureVerifier()
        assert verifier.verify("body", header1, "key", algorithm=HmacAlgorithm.SHA256) is False

    def test_sha512_sig_fails_sha1_verify(self):
        gen512 = SignatureGenerator("key", HmacAlgorithm.SHA512)
        header512 = gen512.generate_header_value("body")
        verifier = SignatureVerifier()
        assert verifier.verify("body", header512, "key", algorithm=HmacAlgorithm.SHA1) is False

    def test_string_algorithm_construction(self):
        gen1 = SignatureGenerator("key", "sha1")
        gen2 = SignatureGenerator("key", HmacAlgorithm.SHA1)
        raw1 = gen1.generate_raw("body")
        raw2 = gen2.generate_raw("body")
        assert raw1 == raw2

    def test_string_algorithm_sha512(self):
        gen = SignatureGenerator("key", "hmac-sha512")
        assert gen.algorithm == HmacAlgorithm.SHA512
        assert len(gen.generate_raw("body")) == 128
