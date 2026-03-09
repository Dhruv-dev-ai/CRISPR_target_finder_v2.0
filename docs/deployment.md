# Deployment Guide

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
streamlit run main.py

# Run REST API (separate terminal)
python api.py
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

This starts:
- **Streamlit app** on port 8501
- **REST API** on port 5000

### Manual Docker Build

```bash
docker build -t crispr-target-finder .
docker run -p 8501:8501 -v crispr-data:/app/user_data crispr-target-finder
```

## Streamlit Cloud

1. Push your code to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Select your repository, branch (`main`), and main file (`main.py`)
5. Click "Deploy"

!!! note
    Streamlit Cloud provides free hosting for public repositories. The app will be accessible at `https://yourusername-crispr-target-finder-main-xxxxx.streamlit.app`.

## Heroku

```bash
# Create Procfile
echo "web: streamlit run main.py --server.port $PORT --server.headless true" > Procfile

# Deploy
heroku create crispr-target-finder
git push heroku main
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `STREAMLIT_SERVER_PORT` | 8501 | Server port |
| `STREAMLIT_SERVER_HEADLESS` | true | Run without browser |
| `FLASK_ENV` | production | Flask environment |

## CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci-cd.yml`) automatically:

1. **Lint**: Runs flake8 on every push/PR
2. **Test**: Runs pytest with coverage on every push/PR
3. **Docker**: Builds and smoke-tests Docker image on `main` branch
