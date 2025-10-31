import json
from typing import Dict, Any, List, Union
import os
import base64
import requests
from tqdm import tqdm
import concurrent.futures
from pathlib import Path
import cv2
import pymupdf 
import numpy as np
import tempfile

class OCRProcessor1:
    def __init__(self, model_name: str = "llama3.2-vision:11b", 
                 base_url: str = "http://localhost:11434/api/generate",
                 max_workers: int = 1):
        
        self.model_name = model_name
        self.base_url = base_url
        self.max_workers = max_workers

    def _encode_image(self, image_path: str) -> str:
        """Convert image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _pdf_to_images(self, pdf_path: str) -> List[str]:
        """
        Convert each page of a PDF to an image using pymupdf.
        Saves each page as a temporary image.
        Returns a list of image paths.
        """
        try:
            doc = pymupdf.open(pdf_path)
            image_paths = []
            
            # Create temporary directory for PDF pages
            temp_dir = tempfile.mkdtemp(prefix="pdf_pages_")
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # 2x resolution for better quality
                
                # Use temp directory with sanitized filename
                temp_path = os.path.join(temp_dir, f"page_{page_num:04d}.png")
                pix.save(temp_path)
                image_paths.append(temp_path)
            
            doc.close()
            return image_paths
        except Exception as e:
            raise ValueError(f"Could not convert PDF to images: {e}")

    def _preprocess_image(self, image_path: str, language: str = "en") -> str:
        """
        Preprocess image before OCR:
        - Convert PDF to image if needed (using pymupdf)
        - Language-specific preprocessing (if applicable)
        - Enhance contrast
        - Reduce noise
        """
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not read image at {image_path}")

        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced)

        # Language-specific thresholding
        if language.lower() in ["japanese", "chinese", "zh", "korean", "ja", "ko"]:
            # For CJK languages adaptive thresholding may work better
            thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2)
            thresh = cv2.bitwise_not(thresh)
        else:
            # Default: Otsu thresholding
            thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            thresh = cv2.bitwise_not(thresh)

        # Save preprocessed image in temp directory
        temp_dir = os.path.dirname(image_path)
        base_name = os.path.basename(image_path)
        preprocessed_path = os.path.join(temp_dir, f"preprocessed_{base_name}")
        cv2.imwrite(preprocessed_path, thresh)

        return preprocessed_path

    def _get_prompt(self, format_type: str, language: str, custom_prompt: str = None) -> str:
        """Get the appropriate prompt based on format type"""
        if custom_prompt and custom_prompt.strip():
            return custom_prompt
        
        prompts = {
            "markdown": f"""Extract all text content from this image in {language} **exactly as it appears**, without modification, summarization, or omission.
                Format the output in markdown:
                - Use headers (#, ##, ###) **only if they appear in the image**
                - Preserve original lists (-, *, numbered lists) as they are
                - Maintain all text formatting (bold, italics, underlines) exactly as seen
                - **Do not add, interpret, or restructure any content**
            """,
            "text": f"""Extract all visible text from this image in {language} **without any changes**.
                - **Do not summarize, paraphrase, or infer missing text.**
                - Retain all spacing, punctuation, and formatting exactly as in the image.
                - If text is unclear or partially visible, extract as much as possible without guessing.
                - **Include all text, even if it seems irrelevant or repeated.** 
            """,
            "json": f"""Extract all text from this image in {language} and format it as JSON, **strictly preserving** the structure.
                - **Do not summarize, add, or modify any text.**
                - Maintain hierarchical sections and subsections as they appear.
                - Use keys that reflect the document's actual structure (e.g., "title", "body", "footer").
                - Include all text, even if fragmented, blurry, or unclear.
            """,
            "structured": f"""Extract all text from this image in {language}, **ensuring complete structural accuracy**:
                - Identify and format tables **without altering content**.
                - Preserve list structures (bulleted, numbered) **exactly as shown**.
                - Maintain all section headings, indents, and alignments.
                - **Do not add, infer, or restructure the content in any way.**
            """,
            "key_value": f"""Extract all key-value pairs from this image in {language} **exactly as they appear**:
                - Identify and extract labels and their corresponding values without modification.
                - Maintain the exact wording, punctuation, and order.
                - Format each pair as 'key: value' **only if clearly structured that way in the image**.
                - **Do not infer missing values or add any extra text.**
            """,
            "table": f"""Extract all tabular data from this image in {language} **exactly as it appears**, without modification, summarization, or omission.
                - **Preserve the table structure** (rows, columns, headers) as closely as possible.
                - **Do not add missing values or infer content**—if a cell is empty, leave it empty.
                - Maintain all numerical, textual, and special character formatting.
                - If the table contains merged cells, indicate them clearly without altering their meaning.
                - Output the table in a structured format such as Markdown, CSV, or JSON, based on the intended use.
            """,
        }
        return prompts.get(format_type, prompts["text"])

    def _process_single_image(self, image_path: str, prompt: str, timeout: int = 30) -> str:
        """Process a single image with the given prompt"""
        image_base64 = self._encode_image(image_path)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "images": [image_base64]
        }
        
        response = requests.post(self.base_url, json=payload, timeout=timeout)
        response.raise_for_status()
        
        return response.json().get("response", "")

    def process_image(self, image_path: str, format_type: str = "markdown", preprocess: bool = True, 
                      custom_prompt: str = None, language: str = "en") -> str:
        """
        Process an image (or PDF) and extract text in the specified format

        Args:
            image_path: Path to the image file or PDF file
            format_type: One of ["markdown", "text", "json", "structured", "key_value", "table"]
            preprocess: Whether to apply image preprocessing
            custom_prompt: If provided, this prompt overrides the default based on format_type
            language: Language code to apply language specific OCR preprocessing
        """
        temp_files_to_cleanup = []
        
        try:
            # If the input is a PDF, process all pages
            if image_path.lower().endswith('.pdf'):
                image_pages = self._pdf_to_images(image_path)
                temp_files_to_cleanup.extend(image_pages)
                
                print(f"Processing PDF with {len(image_pages)} pages")
                responses = []
                
                prompt = self._get_prompt(format_type, language, custom_prompt)
                print(f"Using prompt for format '{format_type}'")
                
                for idx, page_file in enumerate(image_pages):
                    try:
                        # Preprocess if enabled
                        if preprocess:
                            preprocessed_path = self._preprocess_image(page_file, language)
                            temp_files_to_cleanup.append(preprocessed_path)
                            file_to_process = preprocessed_path
                        else:
                            file_to_process = page_file
                        
                        # Process the image
                        result = self._process_single_image(file_to_process, prompt)
                        responses.append(f"Page {idx + 1}:\n{result}")
                        print(f"Processed page {idx + 1}/{len(image_pages)}")
                        
                    except Exception as e:
                        print(f"Error processing page {idx + 1}: {str(e)}")
                        responses.append(f"Page {idx + 1}: Error - {str(e)}")
                
                # Combine all page results
                final_result = "\n\n".join(responses)
                
                # Try to parse as JSON if format is JSON
                if format_type == "json":
                    try:
                        json_data = json.loads(final_result)
                        return json.dumps(json_data, indent=2)
                    except json.JSONDecodeError:
                        return final_result
                
                return final_result
            
            # Process single image (non-PDF)
            else:
                if preprocess:
                    # Create temp file for preprocessing
                    temp_dir = tempfile.mkdtemp(prefix="ocr_preprocess_")
                    preprocessed_path = self._preprocess_image(image_path, language)
                    temp_files_to_cleanup.append(preprocessed_path)
                    temp_files_to_cleanup.append(temp_dir)
                    file_to_process = preprocessed_path
                else:
                    file_to_process = image_path
                
                prompt = self._get_prompt(format_type, language, custom_prompt)
                result = self._process_single_image(file_to_process, prompt)
                
                # Try to parse as JSON if format is JSON
                if format_type == "json":
                    try:
                        json_data = json.loads(result)
                        return json.dumps(json_data, indent=2)
                    except json.JSONDecodeError:
                        return result
                
                return result
                
        except Exception as e:
            return f"Error processing image: {str(e)}"
        
        finally:
            # Clean up all temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.isfile(temp_file):
                        os.remove(temp_file)
                    elif os.path.isdir(temp_file):
                        # Remove directory and all contents
                        import shutil
                        shutil.rmtree(temp_file, ignore_errors=True)
                except Exception as e:
                    print(f"Warning: Could not clean up temporary file {temp_file}: {e}")

    def process_batch(
        self,
        input_path: Union[str, List[str]],
        format_type: str = "markdown",
        recursive: bool = False,
        preprocess: bool = True,
        custom_prompt: str = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process multiple images in batch
        
        Args:
            input_path: Path to directory or list of image paths
            format_type: Output format type
            recursive: Whether to search directories recursively
            preprocess: Whether to apply image preprocessing
            custom_prompt: If provided, this prompt overrides the default for each image
            language: Language code to apply language specific OCR preprocessing
            
        Returns:
            Dictionary with results and statistics
        """
        # Collect all image paths
        image_paths = []
        if isinstance(input_path, str):
            base_path = Path(input_path)
            if base_path.is_dir():
                pattern = '**/*' if recursive else '*'
                for ext in ['.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp']:
                    image_paths.extend(base_path.glob(f'{pattern}{ext}'))
                    image_paths.extend(base_path.glob(f'{pattern}{ext.upper()}'))
            else:
                image_paths = [base_path]
        else:
            image_paths = [Path(p) for p in input_path]

        print(f"Found {len(image_paths)} files to process")
        
        results = {}
        errors = {}
        
        # Process images with progress bar
        if self.max_workers == 1:
            # Sequential processing (recommended for single Ollama instance)
            for path in tqdm(image_paths, desc="Processing images"):
                try:
                    results[str(path)] = self.process_image(
                        str(path), format_type, preprocess, custom_prompt, language
                    )
                except Exception as e:
                    errors[str(path)] = str(e)
                    print(f"\nError processing {path}: {e}")
        else:
            # Parallel processing (only if max_workers > 1)
            with tqdm(total=len(image_paths), desc="Processing images") as pbar:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_path = {
                        executor.submit(
                            self.process_image, str(path), format_type, preprocess, custom_prompt, language
                        ): path
                        for path in image_paths
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_path):
                        path = future_to_path[future]
                        try:
                            results[str(path)] = future.result()
                        except Exception as e:
                            errors[str(path)] = str(e)
                            print(f"\nError processing {path}: {e}")
                        pbar.update(1)

        return {
            "results": results,
            "errors": errors,
            "statistics": {
                "total": len(image_paths),
                "successful": len(results),
                "failed": len(errors)
            }
        }