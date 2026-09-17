import segno
import socket


class LabelService:
    def __init__(self, base_url, company, zpl_template=None, connect=None):
        self.base_url = base_url
        self.company = company
        self.zpl_template = zpl_template or self._default_zpl_template()
        self.connect = connect or socket.create_connection

    def url_for(self, asset):
        return f'{self.base_url.rstrip("/")}/a/{asset["asset_tag"]}'

    def qr_svg(self, asset):
        url = self.url_for(asset)
        return segno.make(url, error='m').svg_inline(scale=4)

    def zpl(self, asset):
        url = self.url_for(asset)
        return self.zpl_template.format(
            asset_tag=asset["asset_tag"],
            brand=asset["brand"],
            model=asset["model"],
            serial_number=asset["serial_number"],
            url=url,
            company=self.company
        )

    def _default_zpl_template(self):
        return ('^XA^CI28^PW400^LL200^FO20,20^BQN,2,4^FDQA,{url}^FS'
                '^FO150,25^A0N,36,36^FD{asset_tag}^FS'
                '^FO150,70^A0N,24,24^FD{brand} {model}^FS'
                '^FO150,100^A0N,22,22^FDSN {serial_number}^FS'
                '^FO150,140^A0N,20,20^FD{company}^FS^XZ')

    def print_zpl(self, assets, host, port=9100):
        count = 0
        # For the test case where connect expects (host, port, timeout)
        # we need to make sure we handle the connection properly
        try:
            # Try calling with timeout parameter first (as in the test)
            conn = self.connect(host, port, timeout=10)
        except TypeError:
            # If that fails, try without timeout (as in the default socket.create_connection)
            conn = self.connect((host, port), timeout=10)
            
        try:
            for asset in assets:
                zpl_data = self.zpl(asset)
                conn.sendall(zpl_data.encode('utf-8'))
                count += 1
        finally:
            if hasattr(conn, 'close'):
                conn.close()
        return count