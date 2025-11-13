from fastapi import APIRouter, UploadFile, File, FastAPI
from fastapi.responses import JSONResponse, Response
from typing import List
from .DataController import DataController
from .llm import LLMService
import base64
import asyncio

app = FastAPI()
router = APIRouter()
data_controller = DataController()
llm_service = LLMService()

@router.post("/upload")
async def upload_file(file: List[UploadFile] = File(...)):
    results = []
    for file in file[:5]:
        
        is_valid, message = data_controller.validate_file(file)
        if not is_valid:
            return JSONResponse(status_code=400, content={"error": message})

        # file_bytes = await file.read()
        # encode_image = base64.b64encode(file_bytes).decode("utf-8")
        new_name = await llm_service.Renamer(file)
        results.append({
            "original_filename": file.filename,
            "new_name": new_name
        })

    return JSONResponse(content={"results": results})


    #     result = data_controller.process_document(file)
    # # return Response(content=base64.b64decode(result["content"][0]), media_type=result["type"], headers={"X-Signal": result["signal"]})
    #     print(type(result['content'][0]))
    #     new_name = llm_service.Renamer(result)
    #     results.append({
    #         "original_filename": file.filename,
    #         "new_name": new_name,
    #         "signal": result["signal"]
    #     })

app.include_router(router)