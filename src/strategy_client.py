"""
Module for handling strategy updates and communication with trading bot
"""
import aiohttp
import json
import asyncio
from typing import Dict, Any


class StrategyRunner:
    def __init__(self, strategy_url: str):
        """
        Constructor accepts the bot URL
        """
        self.strategy_url = strategy_url
    
    async def send_strategy_with_retry(self, strategy_data: Dict[str, Any], max_retries: int = 3):
        for attempt in range(max_retries):
            try:
                await self._send_json_strategy(strategy_data)
                return  # Success
            except Exception as e:
                if attempt < max_retries - 1:
                    pass  # print(f"Error sending data: {e}. Retry {attempt + 1}/{max_retries - 1} in 2 seconds.")
                    await asyncio.sleep(2)  # Short delay for fast recovery
                else:
                    pass  # print(f"Error sending data after {max_retries} attempts: {e}. Giving up.")
                    # Don't block - let other signals process
    
    async def _send_strategy(self, strategy_name: str):
        """
        Asynchronously sends string strategy to the specified URL (for backward compatibility)
        """
        headers = {
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            # Send string payload
            async with session.post(self.strategy_url, data=strategy_name, headers=headers) as response:
                await self._handle_response(response)
                
    async def _send_json_strategy(self, strategy_data: Dict[str, Any]):
        """
        Asynchronously sends JSON strategy to the specified URL
        """
        headers = {
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            # Send JSON payload directly using the json parameter
            async with session.post(self.strategy_url, json=strategy_data, headers=headers) as response:
                await self._handle_response(response)
                
    async def _handle_response(self, response):
        """
        Handles server response
        """
        if response.status == 200:
            if 'application/json' in response.headers.get('Content-Type', ''):
                result = await response.json()
                pass  # print("Executed:", result)
            else:
                result = await response.text()
                pass  # print("Executed:", result)
        else:
            pass  # print(f"Error: {response.status}")
            # text = await response.text()
            pass  # print("Response:", text)
            
    async def call(self, strategy_name: str):
        """
        Starts the strategy sending process (string format)
        """
        await self._send_strategy(strategy_name)
        
    async def call_with_json(self, strategy_data: Dict[str, Any]):
        """
        Starts the strategy sending process (JSON format)
        """
        await self.send_strategy_with_retry(strategy_data)