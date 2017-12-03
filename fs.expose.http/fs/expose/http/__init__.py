from .server import serve


def run(fs, host='127.0.0.1', port=8000):
    server.serve(fs, host, port)
