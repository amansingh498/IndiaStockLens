# IndiaStockLens

IndiaStockLens is a backend-first stock due diligence pipeline for Indian retail investors. The first milestone is a deployable FastAPI service that normalizes data from Anakin Wire sources and returns a stable JSON analysis response.

See [backend/README.md](backend/README.md) for local setup and deployment commands.

## Local app

Run the backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.
