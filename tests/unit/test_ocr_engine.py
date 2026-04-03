import sys
import types

from japim.ocr.engine import OCREngine


class _FakeResult:
    def __init__(self, payload):
        self.json = payload


def test_ocr_engine_falls_back_to_cpu_when_gpu_architecture_is_unsupported(monkeypatch):
    calls: list[str] = []

    class FakePaddleOCR:
        def __init__(
            self,
            *,
            lang,
            use_doc_orientation_classify,
            use_doc_unwarping,
            use_textline_orientation,
            device,
            text_detection_model_dir=None,
            text_recognition_model_dir=None,
            textline_orientation_model_dir=None,
            show_log=False,
            ocr_version=None,
        ):
            calls.append(device)
            if device != "cpu":
                raise RuntimeError("Unsupported GPU architecture")

        def predict(self, image_path):
            return [
                _FakeResult(
                    {
                        "res": {
                            "rec_texts": ["EMAIL abcdef@example.com"],
                            "rec_scores": [0.99],
                            "rec_boxes": [[10, 20, 110, 60]],
                        }
                    }
                )
            ]

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))

    engine = OCREngine(
        backend="paddle",
        lang="korean",
        use_angle_cls=True,
        confidence_threshold=0.1,
        use_gpu=True,
        device="gpu:0",
        show_log=False,
    )

    tokens = engine.recognize("dummy.png", page_no=1)

    assert [token.text for token in tokens] == ["EMAIL abcdef@example.com"]
    assert calls == ["gpu:0", "cpu"]
    assert engine.use_gpu is False
    assert engine.device == "cpu"
