from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timedelta
import logging
import time
import threading
import csv
import io
from fastapi.responses import StreamingResponse

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.services.pnl_service import PnLService
from app.schemas.pnl import PnLSummary, PnLRequest, PnLExportRequest, PnLExportFormat

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Lightweight in-memory TTL cache (15s default) ---
class TtlCache:
    def __init__(self, ttl_seconds: int = 15):
        self.ttl = ttl_seconds
        self.store = {}
    
    def get(self, key):
        if key not in self.store:
            return None
        
        timestamp, data = self.store[key]
        if time.time() - timestamp > self.ttl:
            del self.store[key]
            return None
        
        return data
    
    def set(self, key, data):
        self.store[key] = (time.time(), data)

# Cache for P&L data
_pnl_cache = TtlCache(15)

@router.get("/summary", response_model=PnLSummary)
async def get_pnl_summary(
    start_date: Optional[date] = Query(None, description="Start date of period (default: current month start)"),
    end_date: Optional[date] = Query(None, description="End date of period (default: today)"),
    base_currency: Optional[str] = Query(None, description="Base currency for conversion (default: user's base currency)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get Profit & Loss summary for the specified period
    """
    try:
        # Set default dates if not provided
        if start_date is None:
            start_date = date.today().replace(day=1)  # First day of current month
        if end_date is None:
            end_date = date.today()
        
        # Get user's base currency if not provided
        if base_currency is None:
            base_currency = current_user.preferred_currency.value if current_user.preferred_currency else "USD"
        
        # Create cache key
        cache_key = (str(current_user.id), start_date, end_date, base_currency)
        
        # Check cache
        cached = _pnl_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Calculate P&L
        pnl_service = PnLService(db)
        summary = pnl_service.calculate_pnl(
            user_id=str(current_user.id),
            start_date=start_date,
            end_date=end_date,
            base_currency=base_currency
        )
        
        # Cache the result
        _pnl_cache.set(cache_key, summary)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error calculating P&L: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating Profit & Loss: {str(e)}"
        )

@router.get("/export")
async def export_pnl(
    format: PnLExportFormat = Query(PnLExportFormat.CSV, description="Export format"),
    start_date: Optional[date] = Query(None, description="Start date of period (default: current month start)"),
    end_date: Optional[date] = Query(None, description="End date of period (default: today)"),
    base_currency: Optional[str] = Query(None, description="Base currency for conversion (default: user's base currency)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export Profit & Loss data in specified format
    """
    try:
        pnl_service = PnLService(db)
        summary = pnl_service.calculate_pnl(
            user_id=str(current_user.id),
            start_date=start_date,
            end_date=end_date,
            base_currency=base_currency
        )
        
        # Generate export based on format
        if format == PnLExportFormat.CSV:
            return _generate_csv_export(summary)
        elif format == PnLExportFormat.PDF:
            return _generate_pdf_export(summary)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format: {format}"
            )
        
    except Exception as e:
        logger.error(f"Error exporting P&L: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting Profit & Loss: {str(e)}"
        )

def _generate_csv_export(summary: PnLSummary) -> StreamingResponse:
    """Generate CSV export of P&L data"""
    
    # Create in-memory CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["Profit & Loss Report"])
    writer.writerow([""])
    writer.writerow(["Period", f"{summary.period_start} to {summary.period_end}"])
    writer.writerow(["Base Currency", summary.base_currency])
    writer.writerow([""])
    
    # Summary section
    writer.writerow(["SUMMARY"])
    writer.writerow(["Total Income", format(summary.total_income, ".2f")])
    writer.writerow(["Total Expenses", format(summary.total_expenses, ".2f")])
    writer.writerow(["Net Amount", format(summary.net_amount, ".2f")])
    writer.writerow(["Savings Rate", f"{summary.savings_rate:.1f}%"])
    writer.writerow(["Profit/Loss", "Profit" if summary.is_profitable else "Loss"])
    writer.writerow([""])
    
    # Income by category
    writer.writerow(["INCOME BY SOURCE"])
    writer.writerow(["Category", "Amount", "Percentage", "Transactions"])
    for item in summary.income_by_category:
        writer.writerow([
            item.category,
            format(item.amount_base, ".2f"),
            f"{item.percentage:.1f}%",
            item.transaction_count
        ])
    writer.writerow([""])
    
    # Expenses by category
    writer.writerow(["EXPENSES BY CATEGORY"])
    writer.writerow(["Category", "Amount", "Percentage", "Transactions"])
    for item in summary.expenses_by_category:
        writer.writerow([
            item.category,
            format(item.amount_base, ".2f"),
            f"{item.percentage:.1f}%",
            item.transaction_count
        ])
    writer.writerow([""])
    
    # Exchange rate info
    writer.writerow(["EXCHANGE RATE INFORMATION"])
    writer.writerow(["Policy", summary.exchange_rate_policy])
    if summary.average_exchange_rate:
        writer.writerow(["Average Rate", format(summary.average_exchange_rate, ".4f")])
    
    # Unclassified income
    if summary.has_unclassified_income:
        writer.writerow([""])
        writer.writerow(["NOTE", f"{summary.unclassified_income_count} unclassified income transactions detected"])
    
    # Prepare response
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=profit-loss-{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )

def _generate_pdf_export(summary: PnLSummary) -> dict:
    """Generate PDF export of P&L data"""
    # TODO: Implement PDF generation
    return {
        "message": "PDF export not yet implemented",
        "summary": summary.dict()
    }