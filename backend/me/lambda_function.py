# lambda_me.py
import os, json, base64, hmac, hashlib
import boto3

rds = boto3.client("rds-data")
DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ.get("DB_NAME", "postgres")
APP_SECRET = os.environ["APP_SECRET"].encode()

def verify_session_token(tok):
    try:
        b, sig = tok.rsplit(".", 1)
        expected = hmac.new(APP_SECRET, b.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode())
        if data.get("exp", 0) < __import__("time").time():
            return None
        return int(data.get("aid"))
    except Exception:
        return None

def exec_sql(sql, parameters=None):
    kwargs = dict(resourceArn=DB_CLUSTER_ARN, secretArn=DB_SECRET_ARN, sql=sql, database=DB_NAME)
    if parameters:
        kwargs["parameters"] = parameters
    return rds.execute_statement(**kwargs)

def handler(event, context):
    cookie_header = (event.get("headers") or {}).get("cookie") or (event.get("headers") or {}).get("Cookie")
    if not cookie_header or "rm_session=" not in cookie_header:
        return {"statusCode":401, "body": "not authenticated"}
    tok = None
    for part in cookie_header.split(";"):
        k,v = part.strip().split("=",1)
        if k=="rm_session":
            tok=v
    aid = verify_session_token(tok)
    if not aid:
        return {"statusCode":401, "body": "invalid session"}

    sql = "SELECT athlete_id, display_name FROM users WHERE athlete_id = :aid LIMIT 1"
    res = exec_sql(sql, parameters=[{"name":"aid","value":{"longValue":aid}}])
    records = res.get("records") or []
    if not records:
        return {"statusCode":404,"body":"user not found"}
    rec = records[0]
    # records format: list of field lists, where each field has stringValue/longValue etc
    athlete_id = int(rec[0].get("longValue") or rec[0].get("stringValue"))
    display_name = rec[1].get("stringValue") if rec[1].get("stringValue") else ""
    return {"statusCode":200, "body": json.dumps({"athlete_id": athlete_id, "display_name": display_name}), "headers":{"Content-Type":"application/json"}}
