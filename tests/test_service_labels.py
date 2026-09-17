from src.services.label_service import LabelService


def _asset(brand="Dell", model="Latitude 5540", serial="5CG4321XYZ", tag="NB-0042"):
    return {"id": 1, "asset_tag": tag, "brand": brand, "model": model, "serial_number": serial, "type": "notebook"}


def test_qr_svg_and_zpl():
    service = LabelService(base_url="https://hw.firma.cz", company="Firma s.r.o.")
    svg = service.qr_svg(_asset())
    assert svg.startswith("<svg") and "</svg>" in svg
    zpl = service.zpl(_asset())
    assert zpl.startswith("^XA") and zpl.rstrip().endswith("^XZ")
    assert "NB-0042" in zpl and "Dell Latitude 5540" in zpl and "https://hw.firma.cz/a/NB-0042" in zpl and "Firma s.r.o." in zpl
    custom = LabelService(base_url="https://hw.firma.cz", company="F", zpl_template="^XA^FO10,10^FD{asset_tag}|{serial_number}^FS^XZ").zpl(_asset())
    assert custom == "^XA^FO10,10^FDNB-0042|5CG4321XYZ^FS^XZ"


def test_send_to_network_printer_uses_injected_socket():
    sent = []

    class FakeSocket:
        def __init__(self):
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.closed = True

        def sendall(self, data):
            sent.append(data)

    service = LabelService(base_url="https://hw.firma.cz", company="F", connect=lambda host, port, timeout: (sent.append(("connect", host, port)) or FakeSocket()))
    count = service.print_zpl([_asset(), _asset(tag="NB-0043")], host="10.0.0.50", port=9100)
    assert count == 2 and sent[0] == ("connect", "10.0.0.50", 9100)
    assert all(isinstance(chunk, bytes) and chunk.startswith(b"^XA") for chunk in sent[1:])
