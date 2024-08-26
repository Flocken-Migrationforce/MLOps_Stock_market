from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
# from model import preprocess_data, prepare_datasets, create_model, train_model, validate_model, predict_prices
import models.train_model
import models.predict_model
from visualization.visualize import create_stock_chart
import os
from keras.models import load_model
import httpx  # Example for making async HTTP requests, waiting for processes to finish before calling another HTML
import logging
from datetime import datetime



app = FastAPI()
templates = Jinja2Templates(directory="templates")

# In-memory database for users
users_db = {}

# Pydantic model for a User
class User(BaseModel):
    """Model representing a user in the application."""
    userid: Optional[int] = None
    name: str
    subscription: str

class StockRequest(BaseModel):
    """Model representing a request to predict stock prices."""
    symbol: str
    userid: int  # Include userid in the request to identify the user

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Functions
async def get_next_user_id():
    """Helper function to generate the next user ID."""
    return max(users_db.keys(), default=0) + 1

# App Endpoints
@app.post("/users/")
async def create_user(user: User):
    """
    Create a new user with the specified name and subscription.
    
    Args:
        user (User): The user to create.
    
    Returns:
        User: The created user with a unique ID.
    """
    user_id = get_next_user_id()
    user.userid = user_id
    users_db[user_id] = user
    return user

@app.get("/users/")
async def get_users():
    """
    Retrieve all registered users.
    
    Returns:
        dict: A dictionary of users keyed by user ID.
    """
    return users_db

@app.put("/users/{userid}")
async def update_user(userid: int, user: User):
    """
    Update the name and subscription type of an existing user.
    
    Args:
        userid (int): The ID of the user to update.
        user (User): The new user data.
    
    Returns:
        User: The updated user data.
    """
    if userid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update the user with the new data
    users_db[userid].name = user.name
    users_db[userid].subscription = user.subscription
    return users_db[userid]

@app.delete("/users/{userid}")
async def delete_user(userid: int):
    """
    Delete a user by ID.
    
    Args:
        userid (int): The ID of the user to delete.
    
    Returns:
        dict: A confirmation message indicating the user was deleted.
    """
    if userid not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[userid]
    return {"userid": userid, "deleted": True}

'''
@app.post("/train/")
def train_model(stock_request: StockRequest):
    """
    Train a stock prediction model for the specified symbol.
    
    Args:
        stock_request (StockRequest): The stock symbol and user ID for the request.
    
    Returns:
        dict: A message confirming the model was trained and saved.
    """
    symbol = stock_request.symbol.upper()
    if symbol not in ['AAPL', 'GOOGL', 'EURUSD=X', 'GC=F']:
        raise HTTPException(status_code=400, detail="Unsupported stock symbol")

    try:
        # Assuming the last two parameters in `train_validate_predict` are start_date and end_date
        predictions_val, y_val, _ = train_validate_predict(symbol=symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Model for {symbol} trained and saved successfully."}
'''

'''
@app.post("/predict/")
def predict_stock(stock_request: StockRequest):
    """
    Predict stock prices for the specified symbol.
    
    Only users with a premium subscription can access this feature.
    
    Args:
        stock_request (StockRequest): The stock symbol and user ID for the request.
    
    Returns:
        dict: The predicted stock prices.
    
    Raises:
        HTTPException: If the user is not premium or if the user or model is not found.
    """
    symbol = stock_request.symbol.upper()
    userid = stock_request.userid

    user = users_db.get(userid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.subscription != "premium":
        raise HTTPException(status_code=403, detail="Your membership is not premium. Please upgrade to access this feature.")

    try:
        _, _, predicted_prices = train_validate_predict(symbol=symbol)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "symbol": symbol,
        "predicted_prices": predicted_prices.tolist()
    }
'''

@app.post("/train/")
async def train_model_endpoint(stock_request: StockRequest):
    symbol = stock_request.symbol.upper()
    if symbol not in ['AAPL', 'GOOGL', 'EURUSD=X', 'GC=F']:
        raise HTTPException(status_code=400, detail="Unsupported stock symbol")

    try:
        scaled_data, scaler, _ = preprocess_data(symbol)
        x_train, y_train, x_val, y_val = prepare_datasets(scaled_data)
        model = create_model()
        train_model(model, x_train, y_train)
        rmse, mae, mape, _, _ = validate_model(model, x_val, y_val, scaler)
        model_path = f'models/{symbol}_prediction.h5'
        model.save(model_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Model for {symbol} trained and saved successfully.",
            "metrics": {"RMSE": rmse, "MAE": mae, "MAPE": mape}}


@app.post("/predict/")
async def predict_stock(stock_request: StockRequest):
    symbol = stock_request.symbol.upper()
    userid = stock_request.userid

    user = users_db.get(userid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.subscription != "premium":
        raise HTTPException(status_code=403,
                            detail="Your membership is not premium. Please upgrade to access this feature.")

    try:
        scaled_data, scaler, _ = preprocess_data(symbol)
        model_path = f'models/{symbol}_prediction.h5'
        model = load_model(model_path)
        predicted_prices = predict_prices(model, scaled_data, scaler, prediction_days=7)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "symbol": symbol,
        "predicted_prices": predicted_prices.tolist()
    }


@app.get("/visualize/{symbol}", response_class=HTMLResponse)
async def visualize_stock(request: Request, symbol: str, days: int = 7):
    try:
        scaled_data, scaler, stock_prices_df = preprocess_data(symbol)
        model_path = f'models/{symbol}_prediction.h5'
        model = load_model(model_path)
        predicted_prices = predict_prices(model, scaled_data, scaler, prediction_days=days)
        chart_image = create_stock_chart(stock_prices_df, predicted_prices, symbol)

        return templates.TemplateResponse("stock_visualization.html", {
            "request": request,
            "symbol": symbol,
            "chart_image": chart_image,
            "prediction_days": days
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


"""@app.get("/async-data/")
async def get_async_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
"""

# start app when this file is run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)

# Shutdown logging
@app.on_event("shutdown")
def shutdown_event():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"App was shut down at {current_time}")