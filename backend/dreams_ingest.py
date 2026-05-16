@app.post("/api/dreams/ingest")
async def ingest_dream(request: Request):
    """Receive a dream from the local OpenClaw dream agent and store it."""
    try:
        dream = await request.json()
        if not dream or not isinstance(dream, dict):
            raise HTTPException(status_code=400, detail="Invalid dream payload")

        import json as _json, datetime as _dt
        from pathlib import Path as _Path

        # Ensure ts field exists
        if "ts" not in dream:
            dream["ts"] = _dt.datetime.utcnow().isoformat()

        # Save to local JSON (same file load_dream_log() reads)
        log_path = _Path("signals") / "dream_log.json"
        log_path.parent.mkdir(exist_ok=True)
        existing = []
        if log_path.exists():
            try:
                existing = _json.loads(log_path.read_text())
            except Exception:
                pass
        existing.insert(0, dream)       # newest first
        existing = existing[:100]       # keep last 100
        log_path.write_text(_json.dumps(existing, indent=2, default=str))

        edge = dream.get("edge_level", "?")
        ticker = dream.get("top_ticker", "-")
        print(f"[DREAM-INGEST] Received: edge={edge} ticker={ticker}")

        return {"status": "saved", "edge": edge, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
