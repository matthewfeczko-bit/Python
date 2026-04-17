from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import math

app = FastAPI()


class CalcRequest(BaseModel):
    expression: str


@app.post("/api/calc")
def calculate(req: CalcRequest):
    try:
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        result = eval(req.expression, {"__builtins__": {}}, allowed)
        return {"result": result, "error": None}
    except ZeroDivisionError:
        return {"result": None, "error": "Division by zero"}
    except Exception as e:
        return {"result": None, "error": str(e)}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
