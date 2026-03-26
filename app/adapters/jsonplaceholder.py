from __future__ import annotations

from typing import Any

import httpx

from app.types import ToolAdapter


class JsonPlaceholderPostsAdapter(ToolAdapter):
    name = "api.posts.list"

    async def execute(self, input_data: Any) -> dict[str, Any]:
        payload = input_data if isinstance(input_data, dict) else {}
        user_id = payload.get("userId")
        limit = payload.get("limit", 10)

        if user_id is not None and not isinstance(user_id, int):
            raise ValueError("Invalid input for api.posts.list: 'userId' must be an integer")
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("Invalid input for api.posts.list: 'limit' must be an integer between 1 and 100")

        params: dict[str, Any] = {}
        if user_id is not None:
            params["userId"] = user_id

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://jsonplaceholder.typicode.com/posts", params=params)
            response.raise_for_status()
            posts = response.json()

        if not isinstance(posts, list):
            raise ValueError("Unexpected response format from JSONPlaceholder")

        return {
            "source": "jsonplaceholder",
            "count": min(len(posts), limit),
            "posts": posts[:limit],
        }
