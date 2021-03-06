import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Get tabular neural net Model and haversine dist func
from neuralnet.models import TabularModel
from geo.haversine import haversine_distance

# Training parameters
EPOCHS = 300
BATCH_N = 6000
TEST_SPLIT = 0.2

if __name__ == "__main__":
    # Read in dataset of taxi fares
    df = pd.read_csv('./data/nyctaxifares.csv')

    # Calculate trip distance from coordinates and add column to df
    # Alternate method using apply()
    # df['dist_km'] = df.apply(haversine_distance, axis=1, args=('pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude'))
    df['dist_km'] = haversine_distance(df, 'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude')
    
    # Convert pickup datetime strings to datetime objs
    df['pickup_datetime'] = pd.to_datetime(df['pickup_datetime'])

    # Adjust UTC datetime for EST in New York City
    df['EDTdate'] = df['pickup_datetime'] - pd.Timedelta(hours=4)
    df['hour'] = df['EDTdate'].dt.hour
    df['weekday'] = df['EDTdate'].dt.strftime("%a")

    # Calculate whether the ride time is during rush hour
    def rush_hour(df) -> str:
        if 8 <= df['hour'] <= 9:
            return 'am_rush'
        elif 15 <= df['hour'] <= 19:
            return 'pm_rush'
        else:
            return 'regular'
    df['rush'] = df.apply(rush_hour, axis=1)
 
    # Prepare categorical and continuous values
    cat_cols = ['hour', 'rush', 'weekday']
    cont_cols = ['pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude','passenger_count', 'dist_km']
    
    # Set y column as fare amount (the target value)
    y_col = ['fare_amount']

    # Change categorical values into Category objects with numerical code
    for cat in cat_cols:
        df[cat] = df[cat].astype('category')
    
    # Convert to array for use as PyTorch tensor
    hr = df['hour'].cat.codes.values
    rush = df['rush'].cat.codes.values
    wkdy = df['weekday'].cat.codes.values

    # Stack them column-wise like original data
    cats = np.stack([hr, rush, wkdy], axis=1)

    # One-line alternate list comprehension for categorical values
    # cats = np.stack([df[col].cat.codes.values for col in cat_cols], axis=1)

    # Convert categorical data to PyTorch tensor
    cats = torch.tensor(cats, dtype=torch.int64)

    # Convert continuous values to PyTorch tensor
    conts = np.stack([df[col].values for col in cont_cols], axis=1)
    conts = torch.tensor(conts, dtype=torch.float)

    # Convert target label (taxi fare) into PyTorch tensor
    y = torch.tensor(df[y_col].values, dtype=torch.float)

    # Set embedding sizes (denser vector representation than one hot encoding)
    cat_szs = [len(df[col].cat.categories) for col in cat_cols]
    emb_szs = [(size, min(50,(size+1)//2)) for size in cat_szs]

    # Generate TabularModel obj
    # conts is a 2d tensor, conts.shape[1] = # of cols = # of cont features
    # emb_szs in this case will be size+1//2
    # Total # of in-features will be conts.shape[1] + sum([emb_szs[i][1] for i in emb_szs])
    torch.manual_seed(3349)
    model = TabularModel(emb_szs, conts.shape[1], 1, [200,100], p=0.4) # out_sz = 1

    print(model)

    # Set loss function and optimization algorithm (alternative to stochastic gradient descent)
    criterion = nn.MSELoss() # np.sqrt(MSE) = RMSE
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Train-test split
    test_size = int(BATCH_N*TEST_SPLIT)

    # Data came pre-shuffled, otherwise randomly shuffle beforehand
    cat_train = cats[:BATCH_N-test_size]
    cat_test = cats[BATCH_N-test_size:BATCH_N]
    con_train = conts[:BATCH_N-test_size]
    con_test = conts[BATCH_N-test_size:BATCH_N]

    y_train = y[:BATCH_N-test_size]
    y_test = y[BATCH_N-test_size:BATCH_N]

    # Train for # of epochs
    losses = []
    for i in range(EPOCHS):
        i += 1

        # Forward pass
        y_pred = model(cat_train, con_train)

        # Track error
        loss = torch.sqrt(criterion(y_pred, y_train))
        losses.append(loss)

        if i%10 == 1:
            print(f'Epoch: {i} | Loss: {loss}')

        # Set zero gradient to erase accumulated weight/bias adjustments
        optimizer.zero_grad()
        # Backpropagation to create gradient for this pass
        loss.backward()
        # Adjust weights and biases according to gradient and learning rate
        optimizer.step()

    # Test neural net against values - no training means no gradient
    with torch.no_grad():
        y_val = model(cat_test, con_test)
        loss = torch.sqrt(criterion(y_val, y_test))
        print(f'Test loss is {loss}')

    # See sample of predicted vs actual values
    for i in range(10):
        print(f'Predicted: {y_val[i].item():8.2f} | Actual: {y_test[i].item():8.2f}')

    # Save neural net for future use, if satisfied
    # torch.save(model.state_dict(), 'taxi_model.pt')

#