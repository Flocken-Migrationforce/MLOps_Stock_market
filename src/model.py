# model.py

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential, load_model
from keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_error
from data import get_daily_stock_prices, create_my_dataset






def preprocess_data(symbol, start_date=None, end_date=None, interval='1d'):
    stock_prices_df = get_daily_stock_prices(symbol, start_date=start_date, end_date=end_date, interval=interval)
    df = stock_prices_df['1. open'].values.reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(df)
    return scaled_data, scaler, stock_prices_df

def prepare_datasets(scaled_data, time_step=60):
    train_size = int(len(scaled_data) * 0.8)
    dataset_train = scaled_data[:train_size]
    dataset_val = scaled_data[train_size - time_step:]
    x_train, y_train = create_my_dataset(dataset_train, time_step=time_step)
    x_val, y_val = create_my_dataset(dataset_val, time_step=time_step)
    x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1], 1))
    x_val = np.reshape(x_val, (x_val.shape[0], x_val.shape[1], 1))
    return x_train, y_train, x_val, y_val

def create_model(time_step=60):
    model = Sequential()
    model.add(LSTM(units=96, return_sequences=True, input_shape=(time_step, 1)))
    model.add(Dropout(0.2))
    model.add(LSTM(units=96, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(units=96))
    model.add(Dropout(0.2))
    model.add(Dense(units=1))
    model.compile(loss='mean_squared_error', optimizer='adam')
    return model

def train_model(model, x_train, y_train, epochs=50, batch_size=32):
    model.fit(x_train, y_train, epochs=epochs, batch_size=batch_size)

def validate_model(model, x_val, y_val, scaler):
    predictions_val = model.predict(x_val)
    predictions_val = scaler.inverse_transform(predictions_val)
    y_val = scaler.inverse_transform(y_val.reshape(-1, 1))
    rmse = np.sqrt(mean_squared_error(y_val, predictions_val))
    mae = mean_absolute_error(y_val, predictions_val)
    mape = np.mean(np.abs((y_val - predictions_val) / y_val)) * 100
    return rmse, mae, mape, predictions_val, y_val

def predict_prices(model, scaled_data, scaler, prediction_days, time_step=60):
    last_time_step = scaled_data[-time_step:]
    x_predict = np.reshape(last_time_step, (1, last_time_step.shape[0], 1))
    predicted_prices = []
    for _ in range(prediction_days):
        predicted_price = model.predict(x_predict)
        predicted_prices.append(predicted_price[0, 0])
        x_predict = np.append(x_predict[:, 1:, :], np.reshape(predicted_price, (1, 1, 1)), axis=1)
    predicted_prices = scaler.inverse_transform(np.array(predicted_prices).reshape(-1, 1))
    return predicted_prices