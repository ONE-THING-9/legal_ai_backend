from fastapi.responses import FileResponse
from utils import get_pdf_link_only
from llm import get_llm_response
from schema import GetFirRequest
from logger import logger
import os
from service.session import create_session, save_into_session_db, get_existing_session



async def get_fir_details(request, get_fir_request:GetFirRequest):
    try:
        logger.info(f"Processing summary get_fir_request: police_station={get_fir_request.police_station}, year={get_fir_request.year}, district={get_fir_request.district}, fir_number={get_fir_request.fir_number}")

        # Check for existing session
        existing_session = await get_existing_session(
            request,
            get_fir_request.user_id,
            get_fir_request.fir_number,
            get_fir_request.police_station,
            get_fir_request.district,
            get_fir_request.year
        )
        print(existing_session)

        if existing_session:
            logger.info(f"Found existing session: {existing_session['_id']}")
            pdf_path = existing_session["pdf_link"]
            # Check if PDF file exists
            if not os.path.exists(pdf_path):
                raise Exception("PDF file not found")
                
            return {
                "status": "success",
                "data": {
                    "summary": existing_session["summary"],
                    "session_id": str(existing_session["_id"])
                }
            }

        # Continue with original flow if no existing session found
        pdf_path = get_pdf_link_only(get_fir_request.year, get_fir_request.district, 
                                   get_fir_request.police_station, get_fir_request.fir_number)
        
        # Check if PDF file exists
        if not os.path.exists(pdf_path):
            raise Exception("PDF file not found")
            
        with open('prompts/summary.txt', 'r') as file:
            summary_prompt = file.read().strip()
        
        logger.debug(f"Generated summary prompt: pdf_path={pdf_path}")
        response = await get_llm_response(summary_prompt, pdf_url=pdf_path)
        logger.info("Successfully generated summary")
        text = "TODO"
        session_id = await create_session(request, get_fir_request.user_id,
                                          get_fir_request.police_station, get_fir_request.fir_number)
        logger.info(f"Successfully created session: session_id={session_id}")
        await save_into_session_db(request, {"text": text, "summary": response,
                                             "fir":get_fir_request.fir_number, "year": get_fir_request.year,
                                              "police_station": get_fir_request.police_station,
                                               "district": get_fir_request.district,
                                                "pdf_link":  pdf_path}, session_id, get_fir_request.user_id)
        
        return {
            "status": "success",
            "data": {
                "summary": response,
                "session_id": session_id
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate summary: error={str(e)}")
        raise