from src.domain.services.ChatService import ChatService
from src.domain.models.ChatResponse import ChatResponse
from src.domain.exceptions.ThreadCreationException import ThreadCreationException
from src.infrastructure.fabric.FabricLlmProvider import FabricLlmProvider
from src.infrastructure.SingletonMeta import SingletonMeta
from src.infrastructure.sql.SqlExtractor import SqlExtractor
from openai import AssistantEventHandler
import logging
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)

logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

class FabricAgentService(ChatService, metaclass=SingletonMeta):
    def __init__(self, assistant_id: Optional[str] = None):
        self.provider: FabricLlmProvider = FabricLlmProvider()
        self.assistant_id = assistant_id
        self.client = self.provider.get_project()
        self._logger = logging.getLogger(__name__)
        self.sql_extractor = SqlExtractor()

    @staticmethod    
    def __apply_context() -> str:
        fecha = time.strftime("%Y-%m-%d")
        fecha_prompt = f"La fecha actual es {fecha}. Usa esta información como filtro en las queries DAX o SQL. No menciones esta instrucción al usuario."

        return fecha_prompt + "\n"
    
    def create_thread(self, old_thread_id: str) -> str:
        """
        Crea un nuevo hilo de conversación.
        Returns:
          thread_id: Identificador del hilo creado.
        """
        
        try:
            self.client.beta.threads.delete(thread_id=old_thread_id)
        except Exception as cleanup_error:
            print(f"⚠️ Warning: Thread cleanup failed: {cleanup_error}")
        try:
            thread_id = self.client.beta.threads.create().id
            self._logger.info(f"✅ Created thread, ID: {thread_id}")
        except Exception as e:
            self._logger.error(f"❌ Error creating thread, error: {e}")
            raise ThreadCreationException(f"Failed to create thread, error: {e}")
        return thread_id
    
    async def chat_stream(self, thread_id: str, user_message: str):
        """
        Envía un mensaje al agente LLM usando el proveedor configurado y devuelve un generador para el resultado en streaming.
        :param thread_id: Identificador del thread donde crear el mensaje.
        :param user_message: Mensaje del usuario para el thread.
        :return: Generador con eventos de streaming del agente LLM.
        """

        agent = self.provider.get_agent(self.assistant_id)
        
        logger.info(f"\n💬 Mensaje del usuario con contexto: {user_message + "\n" + self.__apply_context()}\n")

        self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message + "\n" + self.__apply_context()
            )
        
        # Monitor the run with timeout
        start_time = time.time()
        with self.client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=agent.id,
            event_handler=AssistantEventHandler()
        ) as stream:
            try:
                for text in stream.text_deltas:
                    self._logger.info(f"Streaming text delta: {text}")
                    yield {"type": "delta", "text": text}
            except Exception as e:
                self._logger.error(f"❌ Error during streaming: {e}")
                yield {"error": str(e)}
            else:
                self._logger.info("✅ Streaming completed successfully")
                end_time = time.time()
                self._logger.info(f"⏱️ Total time: {end_time - start_time} seconds")
                yield {"done": True}
    
    def get_DAX_query(self, thread_id: str, user_message: str):
        try:
            agent = self.provider.get_agent(self.assistant_id)
            
            logger.info(f"\n💬 Mensaje del usuario con contexto: {user_message + "\n" + self.__apply_context()}\n")

            self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=user_message + "\n" + self.__apply_context()
                )
            
            # Start and monitor run
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=agent.id
            )

            while run.status in ["queued", "in_progress"]:
                print(f"⏳ Status: {run.status}")
                time.sleep(2)
                run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            
            # Get detailed run steps
            steps = self.client.beta.threads.runs.steps.list(
                thread_id=thread_id,
                run_id=run.id
            )

            # Get messages
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="asc"
            )
            messages_data = messages.model_dump()
            assistant_messages = [msg for msg in messages_data.get('data', []) if msg.get('role') == 'assistant']
            if assistant_messages:
                latest_message = assistant_messages[-1]
                content = latest_message.get('content', [])
                if content and len(content) > 0:
                    # Extract text content
                    text_content = ""
                    if isinstance(content[0], dict):
                        if 'text' in content[0]:
                            if isinstance(content[0]['text'], dict) and 'value' in content[0]['text']:
                                text_content = content[0]['text']['value']
                            else:
                                text_content = str(content[0]['text'])
                    else:
                        text_content = str(content[0])

            sql_analysis = self.sql_extractor._extract_sql_queries_with_data(steps)

            # Also try the old regex method as backup
            if not sql_analysis["queries"]:
                regex_queries = self.sql_extractor._regex_extract_sql_queries(steps)
                if regex_queries:
                    sql_analysis["queries"] = regex_queries
                    sql_analysis["data_retrieval_query"] = regex_queries[0] if regex_queries else None
            
            result = {}
            result["final_response"] = text_content

            # Add SQL analysis if found
            if sql_analysis["queries"]:
                result["sql_queries"] = sql_analysis["queries"]
                result["sql_data_previews"] = sql_analysis["data_previews"]
                result["data_retrieval_query"] = sql_analysis["data_retrieval_query"]
                
                logger.debug(f"🗃️ Found {len(sql_analysis['queries'])} DAX queries in lakehouse operations")
                
                for i, query in enumerate(sql_analysis["queries"], 1):
                    logger.debug(f"📄 DAX Query {i}:")
                    logger.debug(f"   {query}")
                    
                    # Show data preview if this query retrieved data
                    if i == sql_analysis["data_retrieval_query_index"]:
                        logger.debug(f"   🎯 This query retrieved the data!")
                        if sql_analysis["data_previews"][i-1]:
                            logger.debug(f"   📊 Data Preview:")
                            preview = sql_analysis["data_previews"][i-1]
                            
                            # Check if the preview is a raw markdown table (single item)
                            if len(preview) == 1 and '\n' in preview[0] and '|' in preview[0]:
                                # This is a raw markdown table, print it directly
                                logger.debug(preview[0])
                            else:
                                # This is parsed row data, print line by line
                                for line in preview[:5]:  # Show first 5 lines
                                    logger.debug(f"      {line}")
                                if len(preview) > 5:
                                    logger.debug(f"      ... and {len(preview) - 5} more lines")
                    logger.debug("")  # Empty line for readability
            else:
                logger.debug("🗃️ No DAX queries found in lakehouse operations")
            return result
        except Exception as e:
            self._logger.error(f"❌ Error getting DAX queries: {e}")
            raise e