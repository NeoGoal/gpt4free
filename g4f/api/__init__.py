from fastapi            import FastAPI, Response, Request
from typing             import List, Union, Any, Dict, AnyStr
from ._tokenizer        import tokenize
from ..                 import BaseProvider

import time
import json
import random
import string
import uvicorn
import nest_asyncio
import g4f

class Api:
    def __init__(self, engine: g4f, debug: bool = True, sentry: bool = False,
                 list_ignored_providers: List[Union[str, BaseProvider]] = None) -> None:
        self.engine = engine
        self.debug = debug
        self.sentry = sentry
        self.list_ignored_providers = list_ignored_providers

        self.app = FastAPI()
        nest_asyncio.apply()

        JSONObject = Dict[AnyStr, Any]
        JSONArray = List[Any]
        JSONStructure = Union[JSONArray, JSONObject]

        @self.app.get("/")
        async def read_root():
            return Response(content=json.dumps({"info": "g4f API"}, indent=4), media_type="application/json")

        @self.app.get("/v1")
        async def read_root_v1():
            return Response(content=json.dumps({"info": "Go to /v1/chat/completions or /v1/models."}, indent=4), media_type="application/json")

        @self.app.get("/v1/models")
        async def models():
            model_list = [{
                'id': model,
                'object': 'model',
                'created': 0,
                'owned_by': 'g4f'} for model in g4f.Model.__all__()]

            return Response(content=json.dumps({
                'object': 'list',
                'data': model_list}, indent=4), media_type="application/json")

        @self.app.get("/v1/models/{model_name}")
        async def model_info(model_name: str):
            try:
                model_info = (g4f.ModelUtils.convert[model_name])

                return Response(content=json.dumps({
                    'id': model_name,
                    'object': 'model',
                    'created': 0,
                    'owned_by': model_info.base_provider
                }, indent=4), media_type="application/json")
            except:
                return Response(content=json.dumps({"error": "The model does not exist."}, indent=4), media_type="application/json")

        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request, item: JSONStructure = None):
            item_data = {
                'model': 'gpt-3.5-turbo',
                'stream': False,
            }

            item_data.update(item or {})
            model = item_data.get('model')
            stream = item_data.get('stream')
            messages = item_data.get('messages')

            try:
                response = g4f.ChatCompletion.create(model=model, stream=stream, messages=messages)
            except:
                return Response(content=json.dumps({"error": "An error occurred while generating the response."}, indent=4), media_type="application/json")

            completion_id = ''.join(random.choices(string.ascii_letters + string.digits, k=28))
            completion_timestamp = int(time.time())

            if not stream:
                prompt_tokens, _ = tokenize(''.join([message['content'] for message in messages]))
                completion_tokens, _ = tokenize(response)

                json_data = {
                    'id': f'chatcmpl-{completion_id}',
                    'object': 'chat.completion',
                    'created': completion_timestamp,
                    'model': model,
                    'choices': [
                        {
                            'index': 0,
                            'message': {
                                'role': 'assistant',
                                'content': response,
                            },
                            'finish_reason': 'stop',
                        }
                    ],
                    'usage': {
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'total_tokens': prompt_tokens + completion_tokens,
                    },
                }

                return Response(content=json.dumps(json_data, indent=4), media_type="application/json")

            def streaming():
                try:
                    for chunk in response:
                        completion_data = {
                            'id': f'chatcmpl-{completion_id}',
                            'object': 'chat.completion.chunk',
                            'created': completion_timestamp,
                            'model': model,
                            'choices': [
                                {
                                    'index': 0,
                                    'delta': {
                                        'content': chunk,
                                    },
                                    'finish_reason': None,
                                }
                            ],
                        }

                        content = json.dumps(completion_data, separators=(',', ':'))
                        yield f'data: {content}\n\n'
                        time.sleep(0.03)

                    end_completion_data = {
                        'id': f'chatcmpl-{completion_id}',
                        'object': 'chat.completion.chunk',
                        'created': completion_timestamp,
                        'model': model,
                        'choices': [
                            {
                                'index': 0,
                                'delta': {},
                                'finish_reason': 'stop',
                            }
                        ],
                    }

                    content = json.dumps(end_completion_data, separators=(',', ':'))
                    yield f'data: {content}\n\n'

                except GeneratorExit:
                    pass

            return Response(content=json.dumps(streaming(), indent=4), media_type="application/json")

        @self.app.post("/v1/completions")
        async def completions():
            return Response(content=json.dumps({'info': 'Not working yet.'}, indent=4), media_type="application/json")

    def run(self, ip):
        split_ip = ip.split(":")
        uvicorn.run(app=self.app, host=split_ip[0], port=int(split_ip[1]), use_colors=False)
