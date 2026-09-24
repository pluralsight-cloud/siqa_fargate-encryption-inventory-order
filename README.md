# Inventory/Orders App

Minimal Flask app for the "Securing a Fargate Deployment with Envelope
Encryption" lab. It has no real database — it just proves that a DB
config value was successfully injected into the container by ECS, and
gives the ALB something meaningful to health-check.

## How it fits the lab

1. `db-config.sample.json` is the sensitive artifact. In the lab, the
   learner encrypts a file like this one and stores the ciphertext in
   Parameter Store as a `SecureString`, encrypted under their
   customer-managed KMS key. It is **not** copied into the Docker image.
2. The task definition's native `secrets` field points at that
   parameter's ARN and injects its value as the `DB_CONFIG` environment
   variable at container launch — this requires the execution role to
   have `kms:Decrypt` on the CMK.
3. At startup, `app.py` reads `DB_CONFIG`, parses it as JSON, and logs
   whether it arrived successfully. That log line is what a learner (or
   grader) checks in CloudWatch Logs to confirm the secrets/KMS wiring
   worked.
4. `/health` returns unhealthy (500) if `DB_CONFIG` never arrived, so a
   broken execution role or KMS policy shows up as a failing ALB target
   instead of a silently-healthy container.
5. `/inventory` and `/orders` return stub data and log a line naming the
   DB host/port/name they'd "query" — reinforcing the backstory without
   needing a real database.

## Endpoints

| Route        | Purpose                                          |
|--------------|---------------------------------------------------|
| `/`          | Lists available endpoints                         |
| `/health`    | ALB target group health check                     |
| `/inventory` | Stub inventory data                                |
| `/orders`    | Stub orders data                                   |

## Build and run locally (optional, for authoring/testing)

```bash
docker build -t inventory-orders-app .
docker run -p 8080:8080 \
  -e DB_CONFIG='{"host":"db.example.internal","port":5432,"dbname":"inventory","username":"app_user"}' \
  inventory-orders-app
curl http://localhost:8080/health
```

## Push to ECR (as done in the lab)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker build -t inventory-orders-app .
docker tag inventory-orders-app:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/inventory-orders-app:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/inventory-orders-app:latest
```
