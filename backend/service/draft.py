from llm import get_llm_response
from schema import DraftRequest
from service.session import get_session_history, save_conversation_into_db
from logger import logger
from config import PATHS
import os


async def process_history(request, user_id, session_id, only_conversation = False):
    result = await get_session_history(request, user_id, session_id)
    if only_conversation:
        if 'draft' in result:
            previous_draft = result['draft']
        else:
            previous_draft = None
        return previous_draft
    summary = result['summary']
    pdf_text = result['text']
    if 'draft' in result:
        previous_draft = result['draft'][-1][1]
    else:
        previous_draft = None
    return summary, pdf_text, previous_draft

async def get_draft(request, draft_request: DraftRequest):
    try:
        logger.info(f"Processing chat draft request")
        if draft_request.user_message is None:
            previous_draft = await process_history(request, draft_request.user_id, draft_request.session_id, only_conversation = True)
            if previous_draft is not None:
                return {
                    "status": "success",
                    "message": previous_draft
                }
        summary, pdf_text, previous_draft = await process_history(request, draft_request.user_id, draft_request.session_id)
        logger.info(f"Summary: {summary}, PDF Text: {pdf_text}, Previous Draft: {previous_draft}")
        
        # Use config for prompt file path
        prompt_path = os.path.join(PATHS["prompts"], 'chat_draft_prompt.txt')
        with open(prompt_path, 'r') as file:
            chat_draft_prompt = file.read().strip()
            
        prompt = chat_draft_prompt.format(
            case_details=summary, # either use summary or full text
            previous_draft=previous_draft,  
            user_message=draft_request.user_message
        )
        response = await get_llm_response(prompt)
        logger.info("Successfully generated chat draft response")

        await save_conversation_into_db(request,draft_request.user_id, draft_request.session_id, draft_request.user_message,
                                  response,  field_name = "draft")
        
        return {
            "status": "success",
            "data": {
                "chat_draft": response
            }
        }
    except Exception as e:
        logger.error(f"Failed to generate chat draft: error={str(e)}, request_data={request}")
        return {
            "status": "error",
            "message": str(e)
        }