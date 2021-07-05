import json

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go
import dash_table
import pandas as pd
import datetime as dt
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials



external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

credentials = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)

gc = gspread.authorize(credentials)

workbook = gc.open_by_key("1yO7zmBlwV3CAnojepXIi7eJymDjW8CGaFZKUPzA2HZ4")
sheet = workbook.worksheet("Sheet1")

data = sheet.get_all_values()
headers = data.pop(0)

df_info = pd.DataFrame(data, columns=headers)

accounts = df_info[df_info.account != ''][['account', 'שם']].rename(columns={'שם': 'name'})

df_info = df_info.rename(columns={'שם': 'Name', 'account': 'Account','סוכר בצום': 'Fasting Sugar', 'A1c': 'A1C',
'תרופת סוכרת 1': 'Sugar Med 1','תרופת סוכרת 2': 'Sugar Med 2','תרופת סוכרת 3': 'Sugar Med 3','תרופת סוכרת 4': 'Sugar Med 4'})
sugar_meds_cols = ['Sugar Med 1', 'Sugar Med 2', 'Sugar Med 3', 'Sugar Med 4']
df_info['Sugar Meds'] = df_info[sugar_meds_cols].apply(lambda row: ','.join(s for s in row.values.astype(str) if len(s) > 1), axis=1)

app.layout = html.Div([
    html.Div([
        html.Img(src=app.get_asset_url('logo 2 shadow.png'), style={'height': '120px', 'width': '600px'})
    ], className='row'),
    html.Div(id='refresh_timestamp', style={'color': '#f5f5f5', 'textAlign': 'center', 'font-size': '25px'}),

    html.Div([
        html.Div(className='two columns'),
        html.Div([
            html.Div(children='''
                        Choose Account
                        ''', className='row', style={'color': '#f5f5f5', 'font-size': '25px'}),
            html.Div([
                dcc.Dropdown(
                    id='xaxis-column',
                    options=[{'label': row['name'], 'value': row['account']} for index, row in accounts.iterrows()],
                    value=accounts.iloc[0]['account'],
                    placeholder=accounts.iloc[0]['name'],
                ), ], className='row', style={'width': '40%', 'display': 'inline-block', 'textAlign': 'left', 'font-size': '25px'}),
            ],className='six columns')
    ], className='row'),

    html.Div([
        html.Div([
            dcc.Graph(
                id='example-graph',
            ),
            dcc.Interval(
                id='interval-component',
                interval=3 * 100000,  # in milliseconds
                n_intervals=0
            ),
        ], className='seven columns', style={'backgroundColor': '#293f4e'}),
        html.Div([
            html.Div(children='''
            Account Information
        ''', style={'color': '#f5f5f5', 'font-size': '25px', 'textAlign': 'center'}),
            html.Div(
                dash_table.DataTable(
                    id='info_table',
                    style_cell={
                        'font_size': '15px',
                        'text_align': 'center'
                    },
                ),
            ),
            ], className='four columns'),
        ], className='row'),
    html.Div([
        html.Div(className='one column'),
        html.Div(children='''
            Last Reading per User
        ''', className='five columns', style={'color': '#f5f5f5', 'font-size': '25px', 'textAlign': 'center'}),
        html.Div(children='''
            Sugar Level Difference Alert Table
        ''', className='five columns', style={'color': '#f5f5f5', 'font-size': '25px', 'textAlign': 'center'}),
        html.Div(className='one column'),
        ], className='row'),
    html.Div([
        html.Div(className='one column'),
        html.Div(
            dash_table.DataTable(
                id='table_last_reading',
                style_cell={
                    'font_size': '15px',
                    'text_align': 'center'
                }
            ), className='five columns'
        ),

        html.Div(
            dash_table.DataTable(
                id='table_sugar_diff',
                style_data={'border': '1px solid red'},
                style_header={'border': '2px solid red'},
                style_cell={
                    'font_size': '15px',
                    'text_align': 'center'
                },
            ), className='five columns'
        ),
        html.Div(className='one column'),
             ], className='row'),
    html.Div(id='intermediate-value', style={'display': 'none'}),
    html.Div(id='intermediate-value-history', style={'display': 'none'})
],  style={
    'verticalAlign': 'middle',
#    'position': 'fixed',
    'margin-left': 0,
    'margin-right': 0,
    'margin-top': 0,
    'margin-bottom': 0,
    'width': '100%',
    'height': '100%',
    'backgroundColor': '#293f4e',
})


@app.callback([dash.dependencies.Output('intermediate-value', 'children'),
               dash.dependencies.Output('intermediate-value-history', 'children'),
               dash.dependencies.Output('refresh_timestamp', 'children')],
              [dash.dependencies.Input('interval-component', 'n_intervals')])
def clean_data(n):
    current_time = dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=3)  # On Heroku date time is UTC
    current_time = "Last Refresh Time: " + current_time.strftime("%d-%b-%Y (%H:%M:%S)")
    today = dt.date.today()
    start_date = today - dt.timedelta(1)
    columns = ["_id", "date", "dateString", "rssi", "device", "direction", "rawbg", "sgv", "type", "utcOffset",
               "sysTime", "User_Site", "Date_Time", "Hour", "Date"]
    sugar_data = pd.DataFrame(columns=columns)
    for account in accounts.account:
        get_string = "https://{}.herokuapp.com/api/v1/entries/sgv.json?find[dateString][$gte]>{}&count=300".format(
            account, start_date)
        data = requests.get(get_string)
        data_json = data.json()
        account_data = pd.DataFrame(data_json)
        if len(account_data) == 0:
            continue
        account_data['User_Site'] = account
        account_data['Date_Time'] = pd.to_datetime(account_data['dateString'])
        account_data['Date_Time_IST'] = pd.to_datetime(account_data['Date_Time'], unit='ms').dt.tz_convert('Israel')
        account_data['Hour'] = account_data['Date_Time_IST'].dt.time
        account_data['Date'] = account_data['Date_Time_IST'].dt.date
        account_data = account_data.set_index('Date_Time_IST')
        account_data = account_data.tz_localize(None)
        account_data['Date_Time'] = account_data['Date_Time'].dt.strftime('%d/%m/%Y %H:%M:%S')
        sugar_data = sugar_data.append(account_data)
    sugar_data = sugar_data.tz_localize(None)
    sugar_data.sgv = sugar_data.sgv.astype(int)
    sugar_data['Color'] = sugar_data['sgv'].apply(lambda x: "Hypo" if x < 70 else ('Hyper' if x > 150 else "Normal"))
    sugar_data['Color_map'] = sugar_data['sgv'].apply(
        lambda x: "rgb(230, 230, 0)" if x < 70 else ('rgb(255, 102, 102)' if x > 150 else "rgb(0, 179, 60)"))

    datasets = {}
    for account in accounts.account:
        datasets[account] = sugar_data[(sugar_data.index >= (dt.datetime.now() - dt.timedelta(hours=24))) & (sugar_data.User_Site == account)].to_json(orient='split', date_format='iso')

#    for column in sugar_data:
#        sugar_data[column] = sugar_data[column].apply(str)

    return json.dumps(datasets), sugar_data.to_json(date_format='iso', orient='split') ,current_time


@app.callback(dash.dependencies.Output('example-graph', 'figure'),
              [dash.dependencies.Input('intermediate-value', 'children'),
              dash.dependencies.Input('interval-component', 'n_intervals'),
              dash.dependencies.Input('xaxis-column', 'value'),]
              )
def update_graph(jsonified_cleaned_data, n, selector):
    datasets = json.loads(jsonified_cleaned_data)
    filtered_df = pd.read_json(datasets[selector], orient='split')
    filtered_df = filtered_df.tz_localize(None)
#    df.sgv = df.sgv.astype(int)
#    df['Color'] = df['sgv'].apply(lambda x: "Hypo" if x < 70 else ('Hyper' if x > 150 else "Normal"))
#    df['Color_map'] = df['sgv'].apply(
#        lambda x: "rgb(230, 230, 0)" if x < 70 else ('rgb(255, 102, 102)' if x > 150 else "rgb(0, 179, 60)"))
#    filtered_df = df[(df.index >= (dt.datetime.now() - dt.timedelta(hours=24))) & (df.User_Site == selector)]
#    filtered_df = last_day_df[last_day_df.User_Site == selector]
    user_name = accounts.set_index('account').loc[selector]['name']
    filtered_fig = go.Figure(data=go.Scatter(x=filtered_df.index, y=filtered_df.sgv, marker_color=filtered_df.Color_map, mode='markers',),
                            layout=go.Layout(
                                    paper_bgcolor= 'rgba(0,0,0,0)',
                                    font={"size": 15, "color": "White"},
                                    title={
                                        'text': f'Last 24 Hours Reading of {user_name}',
                                        'xanchor': 'center',
                                        'yanchor': 'top',
                                        'y':0.9,
                                        'x': 0.5},
                                    titlefont={"size": 25, "color": "White"},
                                    xaxis_title="Date/Time",
                                    yaxis_title="Sugar Level",
                                    margin={"t": 80, "b": 120},
                                    )
                             )
    return filtered_fig


@app.callback([dash.dependencies.Output('table_last_reading', 'data'),
               dash.dependencies.Output('table_last_reading', 'columns')],
              [dash.dependencies.Input('intermediate-value-history', 'children'),
               dash.dependencies.Input('interval-component', 'n_intervals'),
               ]
              )
def update_last_reading_table(jsonified_cleaned_data, n):
#    datasets = json.loads(jsonified_cleaned_data)
#    df = pd.DataFrame(columns=['_id', 'date', 'dateString', 'rssi', 'device', 'direction', 'rawbg',
#                               'sgv', 'type', 'utcOffset', 'sysTime', 'User_Site', 'Date_Time', 'Hour',
#                               'Date', 'Color', 'Color_map'])
#    for account in datasets.keys():
#        df = df.append(pd.read_json(datasets[account], orient='split'))
#    df = df.tz_localize(None)
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    df = df.tz_localize(None)
    df.sgv = df.sgv.astype(int)
    df = df.reset_index()
    df = df.rename(columns={'index': 'Date_Time_IST'})
    df['Date'] = df['Date'].dt.strftime('%d-%b-%Y')
    df_max = df[df.groupby('User_Site').Date_Time_IST.transform('max') == df.Date_Time_IST][
        ['User_Site', 'Date', 'Hour', 'sgv']]
    df_max = df_max.merge(accounts, left_on='User_Site', right_on='account')
    df_max = df_max[['account', 'name', 'Date', 'Hour', 'sgv']].rename(columns={'account': 'Account', 'name': 'Name'})
    df_max_columns = [{"name": i, "id": i} for i in df_max.columns]
    df_max_data = df_max.to_dict('records')
    return df_max_data, df_max_columns


@app.callback([dash.dependencies.Output('table_sugar_diff', 'data'),
               dash.dependencies.Output('table_sugar_diff', 'columns')],
              [dash.dependencies.Input('intermediate-value-history', 'children'),
               dash.dependencies.Input('interval-component', 'n_intervals'),]
              )
def update_sugar_diff_table(jsonified_cleaned_data, n):
#    datasets = json.loads(jsonified_cleaned_data)
#    df = pd.DataFrame(columns=['_id', 'date', 'dateString', 'rssi', 'device', 'direction', 'rawbg',
#                               'sgv', 'type', 'utcOffset', 'sysTime', 'User_Site', 'Date_Time', 'Hour',
#                               'Date', 'Color', 'Color_map'])
#    for account in datasets.keys():
#        df = df.append(pd.read_json(datasets[account], orient='split'))
#    df = df.tz_localize(None)
    df = pd.read_json(jsonified_cleaned_data, orient='split')
    df = df.tz_localize(None)
    df.sgv = df.sgv.astype(int)
    last_day_df = df[df.index >= (dt.datetime.now() - dt.timedelta(hours=24))]
    last_day_df = last_day_df.reset_index()
    last_day_df['Date'] = last_day_df['index'].dt.strftime('%d-%b-%Y')
    last_day_df['Aggregated_Hour'] = last_day_df.Hour.astype(str).str[:2]
    last_day_df.sgv = last_day_df.sgv.astype(int)
    sugar_diff = pd.DataFrame(last_day_df.groupby(['User_Site', 'Date', 'Aggregated_Hour']).sgv.max() - last_day_df.groupby(
        ['User_Site', 'Date', 'Aggregated_Hour']).sgv.min())
    sugar_diff = sugar_diff.rename(columns={
        'sgv': 'Sugar_Difference',
    })
    sugar_diff = sugar_diff.reset_index()
    sugar_diff = sugar_diff.merge(accounts, left_on='User_Site', right_on='account')
    sugar_diff = sugar_diff[['account', 'name', 'Date', 'Aggregated_Hour', 'Sugar_Difference']].rename(columns={'account': 'Account', 'name': 'Name'})
    sugar_diff_columns = [{"name": i, "id": i} for i in sugar_diff.columns]
    sugar_diff_data = sugar_diff[sugar_diff.Sugar_Difference >= 100].reset_index().to_dict('records')

    return sugar_diff_data, sugar_diff_columns


@app.callback([dash.dependencies.Output('info_table', 'data'),
               dash.dependencies.Output('info_table', 'columns')],
              [dash.dependencies.Input('xaxis-column', 'value')])
def update_info_table(selector):
    client_data = df_info[df_info['Account'] == selector].to_dict('records')
    client_columns = [{"name": i, "id": i} for i in ['Account', 'Name', 'Fasting Sugar', 'A1C', 'Sugar Meds']]

    return client_data, client_columns



if __name__ == '__main__':
    app.run_server(debug=True)