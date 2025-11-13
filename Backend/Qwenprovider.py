from openai import OpenAI
import base64
import os
from typing import Union, List
import requests
import ollama


class QwenProvider:
    def __init__(self, api_key: str = "", base_url: str = "http://localhost:11434", model_name: str = "qwen2.5vl:7b", use_ollama: bool = True):
        self.model_name = model_name
        self.use_ollama = use_ollama
        
        if use_ollama:
            # Using Ollama - we'll use the ollama library directly
            self.base_url = base_url
        else:
            # Using Alibaba Cloud OpenAI-compatible API
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

    def encode_image(self, image_path: str) -> str:
        """Convert image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def process_image(self, image_path: str, format_type: str = "markdown",
                     custom_prompt: str = None, language: str = "en") -> str:
        """
        Process an image and extract text using either Ollama or Alibaba Cloud Qwen API

        Args:
            image_path: Path to the image file
            format_type: One of ["markdown", "text", "json", "structured", "key_value", "table"]
            custom_prompt: If provided, this prompt overrides the default based on format_type
            language: Language code to specify the language of the text
        """
        if self.use_ollama:
            # Process using Ollama
            image_base64 = self.encode_image(image_path)
            
            prompt_text = self._get_prompt(format_type, language, custom_prompt)
            
            try:
                response = ollama.chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt_text,
                            "images": [image_base64]  # Ollama format
                        }
                    ]
                )
                return response['message']['content']
                
            except Exception as e:
                return f"Error processing image with Ollama: {str(e)}"
        else:
            # Process using Alibaba Cloud OpenAI-compatible API
            image_base64 = self.encode_image(image_path)

            # Construct the message with image and text
            message_content = []

            # Add text prompt
            prompt_text = self._get_prompt(format_type, language, custom_prompt)
            message_content.append({"type": "text", "text": prompt_text})

            # Add image
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            })

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": message_content
                        }
                    ],
                    max_tokens=4096
                )

                return response.choices[0].message.content

            except Exception as e:
                return f"Error processing image with Qwen API: {str(e)}"

    def process_images_batch(self, image_paths: List[str], format_type: str = "markdown",
                           custom_prompt: str = None, language: str = "en") -> str:
        """
        Process multiple images - simplified for this implementation to work with both providers
        """
        # For simplicity with Ollama, we'll process images one by one
        results = []
        for image_path in image_paths:
            result = self.process_image(image_path, format_type, custom_prompt, language)
            results.append(result)
        
        return "\n\n".join(results)

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

    def generate_file_name(self, prompt: str) -> str:
        """
        Generate a descriptive file name based on the provided prompt
        """
        if self.use_ollama:
            # Use Ollama for file naming
            try:
                response = ollama.chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert file renamer. Based on the context provided, generate a concise, descriptive file name without any additional text or explanation. Just provide the file name."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                return response['message']['content'].strip()
                
            except Exception as e:
                return f"Error generating file name with Ollama: {str(e)}"
        else:
            # Use Alibaba Cloud OpenAI-compatible API for file naming
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert file renamer. Based on the context provided, generate a concise, descriptive file name without any additional text or explanation. Just provide the file name."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=100
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                return f"Error generating file name with Qwen API: {str(e)}"