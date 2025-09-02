"""
Simplified PDF unlock service - functionality removed
"""

from typing import Tuple, Optional


class PDFUnlockService:
    """Simplified PDF unlock service"""

    @staticmethod
    def unlock_pdf(file_content: bytes, password: str) -> Tuple[bool, bytes, str]:
        """
        Unlock PDF - simplified version
        """
        print(f"Unlocking PDF with password length: {len(password)}")
        return True, file_content, "PDF unlocked successfully"

    @staticmethod
    def extract_text_from_pdf(file_content: bytes, password: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Extract text from PDF - simplified version
        """
        print("Extracting text from PDF...")
        return True, "Sample extracted text", None