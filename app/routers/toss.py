from fastapi import APIRouter, HTTPException, Query
from app.services import toss_api

router = APIRouter(prefix="/toss", tags=["toss"])


@router.get("/accounts")
def list_toss_accounts():
    try:
        return toss_api.get_accounts()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"토스증권 API 오류: {e}")


@router.get("/holdings")
def get_toss_holdings(account_seq: str = Query(...)):
    try:
        return toss_api.get_holdings(account_seq)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"토스증권 API 오류: {e}")
