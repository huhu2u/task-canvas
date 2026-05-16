#!/usr/bin/env python3
"""带 charset=utf-8 的静态文件服务器，替代 python3 -m http.server"""
import http.server
import os

class UTF8Handler(http.server.SimpleHTTPRequestHandler):
    def guess_type(self, path):
        ctype = super().guess_type(path)
        # 对 HTML 文件强制加 charset=utf-8
        if isinstance(ctype, str) and 'text/html' in ctype and 'charset' not in ctype:
            ctype = 'text/html; charset=utf-8'
        elif isinstance(ctype, str) and 'text/' in ctype and 'charset' not in ctype:
            ctype += '; charset=utf-8'
        return ctype

    def log_message(self, format, *args):
        pass  # 静默日志

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    os.chdir('/root/.openclaw/workspace')
    with http.server.HTTPServer(('0.0.0.0', port), UTF8Handler) as httpd:
        print(f'Serving on port {port}', flush=True)
        httpd.serve_forever()
