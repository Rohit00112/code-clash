"""Dynamic challenge loader service - loads questions and test cases from files"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.core.exceptions import ResourceNotFoundError, FileSystemError
import logging

logger = logging.getLogger(__name__)


class ChallengeLoader:
    """Dynamic challenge loader - automatically detects and loads challenges"""
    
    _CACHE_TTL = 5  # seconds

    def __init__(self):
        self.questions_dir = Path(settings.get_questions_dir())
        self.testcases_dir = Path(settings.get_testcases_dir())
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_time: float = 0

        # Create directories if they don't exist
        self.questions_dir.mkdir(parents=True, exist_ok=True)
        self.testcases_dir.mkdir(parents=True, exist_ok=True)

    def invalidate_cache(self):
        """Clear the questions cache so next call re-scans the filesystem"""
        self._cache = None
        self._cache_time = 0
    
    def get_available_questions(self) -> List[Dict[str, Any]]:
        """
        Automatically detect questions by scanning PDF files

        Returns:
            List of question metadata
        """
        # Return cached result if fresh
        if self._cache is not None and (time.time() - self._cache_time) < self._CACHE_TTL:
            return self._cache

        questions = []

        try:
            # Find all PDF files matching pattern question*.pdf
            pdf_files = sorted(self.questions_dir.glob("question*.pdf"))
            
            for pdf_path in pdf_files:
                question_id = pdf_path.stem  # e.g., "question1"
                
                # Check if corresponding test case file exists
                testcase_path = self.testcases_dir / f"{question_id}.json"
                
                if testcase_path.exists():
                    try:
                        # Load test case metadata
                        with open(testcase_path, 'r', encoding='utf-8') as f:
                            testcase_data = json.load(f)
                        
                        # Extract question number
                        question_number = int(question_id.replace("question", ""))
                        
                        questions.append({
                            "id": question_id,
                            "number": question_number,
                            "title": testcase_data.get("title", f"Challenge {question_number}"),
                            "function_name": testcase_data.get("function_name", "solution"),
                            "pdf_path": str(pdf_path),
                            "testcase_path": str(testcase_path),
                            "pdf_available": True,
                            "total_test_cases": len(testcase_data.get("test_cases", [])),
                            "sample_test_cases": sum(1 for tc in testcase_data.get("test_cases", []) if tc.get("is_sample", False)),
                            "max_score": 100  # Default score
                        })
                        
                        logger.info(f"Loaded question: {question_id}")
                    
                    except Exception as e:
                        logger.error(f"Error loading test cases for {question_id}: {e}")
                        continue
                else:
                    logger.warning(f"PDF found but no test cases: {question_id}")
            
            result = sorted(questions, key=lambda x: x["number"])
            self._cache = result
            self._cache_time = time.time()
            return result

        except Exception as e:
            logger.error(f"Error scanning questions directory: {e}")
            raise FileSystemError(f"Failed to load questions: {str(e)}")
    
    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific question metadata
        
        Args:
            question_id: Question identifier (e.g., "question1")
            
        Returns:
            Question metadata or None
        """
        questions = self.get_available_questions()
        return next((q for q in questions if q["id"] == question_id), None)
    
    def load_test_cases(self, question_id: str) -> Dict[str, Any]:
        """
        Load test cases for a question
        
        Args:
            question_id: Question identifier
            
        Returns:
            Test case data
        """
        testcase_path = self.testcases_dir / f"{question_id}.json"
        
        if not testcase_path.exists():
            raise ResourceNotFoundError(f"Test cases for {question_id}")
        
        try:
            with open(testcase_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Auto-mark first 2 as sample if not specified
            test_cases = data.get("test_cases", [])
            for idx, tc in enumerate(test_cases):
                if "is_sample" not in tc:
                    tc["is_sample"] = idx < 2
                if "id" not in tc:
                    tc["id"] = idx + 1
            
            return {
                "function_name": data.get("function_name", "solution"),
                "test_cases": test_cases,
                "total_test_cases": len(test_cases),
                "sample_test_cases": sum(1 for tc in test_cases if tc.get("is_sample", False)),
                "hidden_test_cases": sum(1 for tc in test_cases if not tc.get("is_sample", False))
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {testcase_path}: {e}")
            raise FileSystemError(f"Invalid test case file for {question_id}")
        except Exception as e:
            logger.error(f"Error loading test cases for {question_id}: {e}")
            raise FileSystemError(f"Failed to load test cases: {str(e)}")
    
    def get_sample_test_cases(self, question_id: str) -> List[Dict[str, Any]]:
        """
        Get only sample test cases (for test run)
        
        Args:
            question_id: Question identifier
            
        Returns:
            List of sample test cases
        """
        data = self.load_test_cases(question_id)
        return [tc for tc in data["test_cases"] if tc.get("is_sample", False)]
    
    def get_all_test_cases(self, question_id: str) -> List[Dict[str, Any]]:
        """
        Get all test cases (for submission)
        
        Args:
            question_id: Question identifier
            
        Returns:
            List of all test cases
        """
        data = self.load_test_cases(question_id)
        return data["test_cases"]
    
    def get_pdf_path(self, question_id: str) -> Path:
        """
        Get PDF file path for a question
        
        Args:
            question_id: Question identifier
            
        Returns:
            Path to PDF file
        """
        pdf_path = self.questions_dir / f"{question_id}.pdf"
        
        if not pdf_path.exists():
            raise ResourceNotFoundError(f"PDF for {question_id}")
        
        return pdf_path
    
    def get_next_question_id(self) -> str:
        """Get the next available question ID (e.g., 'question4' if 1-3 exist)"""
        existing = self.get_available_questions()
        if not existing:
            return "question1"
        max_num = max(q["number"] for q in existing)
        return f"question{max_num + 1}"

    def save_question(self, question_id: str, pdf_bytes: bytes, testcase_json: dict) -> Dict[str, Any]:
        """Save uploaded question files to filesystem"""
        pdf_path = self.questions_dir / f"{question_id}.pdf"
        testcase_path = self.testcases_dir / f"{question_id}.json"

        pdf_path.write_bytes(pdf_bytes)

        with open(testcase_path, 'w', encoding='utf-8') as f:
            json.dump(testcase_json, f, indent=2, ensure_ascii=False)

        self.invalidate_cache()
        logger.info(f"Saved question: {question_id}")
        return self.get_question(question_id)

    def delete_question(self, question_id: str) -> bool:
        """Delete question PDF and test case files"""
        pdf_path = self.questions_dir / f"{question_id}.pdf"
        testcase_path = self.testcases_dir / f"{question_id}.json"

        deleted = False
        if pdf_path.exists():
            pdf_path.unlink()
            deleted = True
        if testcase_path.exists():
            testcase_path.unlink()
            deleted = True

        if deleted:
            self.invalidate_cache()
            logger.info(f"Deleted question: {question_id}")
        return deleted

    def validate_question_exists(self, question_id: str) -> bool:
        """
        Check if question exists
        
        Args:
            question_id: Question identifier
            
        Returns:
            True if question exists
        """
        pdf_path = self.questions_dir / f"{question_id}.pdf"
        testcase_path = self.testcases_dir / f"{question_id}.json"
        
        return pdf_path.exists() and testcase_path.exists()


# Singleton instance
challenge_loader = ChallengeLoader()
