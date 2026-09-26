from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/"
)
async def root():
    return {"status": "root_ok"}

@app.api_route("/{full_path:path}", methods=["GET","POST","PUT","DELETE"])
async def catch_all(full_path: str, request: Request):
    return {"path_received": full_path, "url": str(request.url), "scope_path": request.scope.get("path"), "root_path": request.scope.get("root_path")}