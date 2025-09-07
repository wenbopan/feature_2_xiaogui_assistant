# Environment Setup

This application requires specific environment variables to be set before running.

## Required Environment Variables

### API Keys
- `GEMINI_API_KEY` - Your Google Gemini API key
- `QWEN_API_KEY` - Your Qwen API key

## Setting Environment Variables

### Option 1: Permanent Setup (Recommended)
Add to your `~/.zshrc` file:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export QWEN_API_KEY="your-qwen-api-key"
```

Then reload your shell:
```bash
source ~/.zshrc
```

### Option 2: Temporary Setup
Set for current session only:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export QWEN_API_KEY="your-qwen-api-key"
```

### Option 3: One-time Setup
Set before running the startup script:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export QWEN_API_KEY="your-qwen-api-key"
./startup.sh
```

## Optional Environment Variables

The following variables have sensible defaults but can be overridden:

- `DATABASE_URL` - PostgreSQL connection string
- `POSTGRES_HOST` - Database host (default: localhost)
- `POSTGRES_PORT` - Database port (default: 5432)
- `POSTGRES_USER` - Database user (default: current user)
- `POSTGRES_PASSWORD` - Database password (default: password)
- `POSTGRES_DB` - Database name (default: legal_docs_dev)
- `MINIO_ENDPOINT` - MinIO endpoint (default: localhost:9000)
- `MINIO_ACCESS_KEY` - MinIO access key (default: admin)
- `MINIO_SECRET_KEY` - MinIO secret key (default: password123)
- `MINIO_BUCKET` - MinIO bucket name (default: legal-docs)
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka servers (default: localhost:9092)
- `LOG_LEVEL` - Logging level (default: INFO)

## Verification

To verify your environment variables are set correctly:

```bash
echo "GEMINI_API_KEY: $GEMINI_API_KEY"
echo "QWEN_API_KEY: $QWEN_API_KEY"
```

## Security Notes

- Never commit API keys to version control
- Use environment variables instead of hardcoded values
- Consider using a secrets management tool for production deployments
