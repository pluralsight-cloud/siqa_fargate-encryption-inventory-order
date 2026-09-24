import json
import logging
import os
import sys
import threading
import time

from flask import Flask, jsonify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("inventory-orders-app")

app = Flask(__name__)

DB_CONFIG = None
DB_CONFIG_ERROR = None


def load_db_config():
    """Parse the DB_CONFIG env var. ECS injects this at launch via the task
    definition's native `secrets` field, pulling from an SSM Parameter Store
    SecureString that was encrypted under the lab's customer-managed KMS key.
    """
    global DB_CONFIG, DB_CONFIG_ERROR
    raw = os.environ.get("DB_CONFIG")

    if not raw:
        DB_CONFIG_ERROR = "DB_CONFIG environment variable is not set"
        return

    try:
        DB_CONFIG = json.loads(raw)
    except json.JSONDecodeError as exc:
        DB_CONFIG_ERROR = f"DB_CONFIG could not be parsed as JSON: {exc}"


def log_startup_banner():
    log.info("=" * 64)
    log.info("  Inventory/Orders Service - Starting Up")
    log.info("=" * 64)

    if DB_CONFIG_ERROR:
        log.error("[FAIL] %s", DB_CONFIG_ERROR)
        log.error("[FAIL] Secret was NOT injected correctly. Check the task")
        log.error("[FAIL] definition's 'secrets' field and the execution")
        log.error("[FAIL] role's KMS permissions.")
        return

    log.info("[OK] DB_CONFIG environment variable is set.")
    log.info("[OK] Database host: %s", DB_CONFIG.get("host", "<missing>"))
    log.info("[OK] Database port: %s", DB_CONFIG.get("port", "<missing>"))
    log.info("[OK] Database name: %s", DB_CONFIG.get("dbname", "<missing>"))
    log.info("[OK] Database user: %s", DB_CONFIG.get("username", "<missing>"))
    log.info("[OK] Secret successfully injected via Parameter Store!")
    log.info("=" * 64)
    log.info("  Application is running.")
    log.info("=" * 64)


def heartbeat_loop():
    while True:
        time.sleep(30)
        if DB_CONFIG_ERROR:
            log.warning("[HEARTBEAT] unhealthy - %s", DB_CONFIG_ERROR)
        else:
            log.info(
                "[HEARTBEAT] App is healthy - db=%s:%s/%s",
                DB_CONFIG.get("host"),
                DB_CONFIG.get("port"),
                DB_CONFIG.get("dbname"),
            )


load_db_config()
log_startup_banner()
threading.Thread(target=heartbeat_loop, daemon=True).start()


@app.route("/")
def index():
    return jsonify(
        service="inventory-orders-app",
        endpoints=["/health", "/inventory", "/orders"],
    )


@app.route("/health")
def health():
    """Health check target for the ALB target group. Fails unhealthy if the
    DB config never arrived, which surfaces a broken secrets/KMS wiring as
    a failing target instead of a silently-healthy container."""
    if DB_CONFIG_ERROR:
        log.warning("[HEALTH] Unhealthy - %s", DB_CONFIG_ERROR)
        return jsonify(status="unhealthy", reason=DB_CONFIG_ERROR), 500

    return (
        jsonify(
            status="healthy",
            db_host=DB_CONFIG.get("host"),
            db_port=DB_CONFIG.get("port"),
            db_name=DB_CONFIG.get("dbname"),
        ),
        200,
    )


@app.route("/inventory")
def inventory():
    if DB_CONFIG_ERROR:
        return jsonify(error=DB_CONFIG_ERROR), 500

    log.info(
        "[QUERY] Would query inventory from %s:%s/%s",
        DB_CONFIG.get("host"),
        DB_CONFIG.get("port"),
        DB_CONFIG.get("dbname"),
    )

    # Stub data - no real database is provisioned for this lab. The point
    # is proving the app can see its DB config, not running real queries.
    sample_inventory = [
        {"sku": "WIDGET-100", "name": "Standard Widget", "quantity": 4500},
        {"sku": "WIDGET-200", "name": "Deluxe Widget", "quantity": 1200},
        {"sku": "GADGET-050", "name": "Compact Gadget", "quantity": 8300},
    ]
    return jsonify(
        source=f"{DB_CONFIG.get('host')}/{DB_CONFIG.get('dbname')}",
        items=sample_inventory,
    )


@app.route("/orders")
def orders():
    if DB_CONFIG_ERROR:
        return jsonify(error=DB_CONFIG_ERROR), 500

    log.info(
        "[QUERY] Would query orders from %s:%s/%s",
        DB_CONFIG.get("host"),
        DB_CONFIG.get("port"),
        DB_CONFIG.get("dbname"),
    )

    sample_orders = [
        {"order_id": "ORD-1001", "status": "shipped", "total": 129.99},
        {"order_id": "ORD-1002", "status": "processing", "total": 54.50},
        {"order_id": "ORD-1003", "status": "delivered", "total": 899.00},
    ]
    return jsonify(
        source=f"{DB_CONFIG.get('host')}/{DB_CONFIG.get('dbname')}",
        items=sample_orders,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
