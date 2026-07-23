"""Helper: read Netspace cookie file from stdin, print base64 for use as YT_COOKIES."""
import sys, base64
data = sys.stdin.read()
b64 = base64.b64encode(data.encode("utf-8")).decode("utf-8")
print(b64)
