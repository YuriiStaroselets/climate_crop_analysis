import csv
import io
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import ClimateData
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO
from sklearn.linear_model import LinearRegression
from django.db.models import OuterRef, Subquery
from sklearn.metrics import r2_score


def index(request):
    has_data = ClimateData.objects.exists()

    coordinates = []
    if has_data:
        # Беремо останні дані по регіонах
        latest_data = ClimateData.objects.order_by('-year', '-month')
        seen = set()
        for entry in latest_data:
            key = (entry.region,)
            if key not in seen:
                seen.add(key)
                coordinates.append({
                    'region': entry.region,
                    'lat': entry.latitude,
                    'lon': entry.longitude,
                    'yield': entry.yield_value,
                })

    return render(request, 'data/index.html', {
        'has_data': has_data,
        'map_data': coordinates
    })


def upload_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        next(io_string)  # Пропустити заголовок
        for row in csv.reader(io_string):
            ClimateData.objects.create(
                year=int(row[0]),
                month=int(row[1]),
                region=row[2],
                crop=row[3],
                temperature=float(row[4]),
                rainfall=float(row[5]),
                uv_index=float(row[6]),
                soil_quality=float(row[7]),
                yield_value=float(row[8]),
                latitude=float(row[9]),
                longitude=float(row[10])
            )
        return redirect('index')
    return render(request, 'data/upload.html')


def analytics(request):
    data = ClimateData.objects.all().values()
    df = pd.DataFrame(data)
    if df.empty:
        return render(request, 'data/analytics.html', {'error': 'No data available'})

    scale_options = [1, 5, 10, 30, 50, 100]
    scale = int(request.GET.get('scale', 10))  # за замовчуванням 10 років
    selected_region = request.GET.get('region', '')  # обраний регіон (або всі)

    last_year = df['year'].max()
    df = df[df['year'] >= last_year - scale + 1]

    regions = sorted(df['region'].unique())
    if selected_region:
        df = df[df['region'] == selected_region]

    df['year_month'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2)

    # Агрегація: середнє за місяць для кожного регіону
    df_plot = df.groupby(['year_month', 'region'])['yield_value'].mean().reset_index()

    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df_plot, x='year_month', y='yield_value', hue='region')
    plt.title(f'Урожайність за останні {scale} років' + (f" ({selected_region})" if selected_region else ""))
    plt.xticks(rotation=45)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    graphic = base64.b64encode(image_png).decode('utf-8')

    return render(request, 'data/analytics.html', {
        'chart': graphic,
        'scale': scale,
        'scale_options': scale_options,
        'regions': regions,
        'selected_region': selected_region
    })


def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="climate_data_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'year', 'month', 'region', 'crop',
        'temperature', 'rainfall', 'uv_index',
        'soil_quality', 'yield_value', 'latitude', 'longitude'
    ])
    for d in ClimateData.objects.all():
        writer.writerow([
            d.year, d.month, d.region, d.crop,
            d.temperature, d.rainfall, d.uv_index,
            d.soil_quality, d.yield_value,
            d.latitude, d.longitude
        ])
    return response


def map_view(request):
    latest_entries = ClimateData.objects.filter(
        region=OuterRef('region')
    ).order_by('-year', '-month')

    records = (
        ClimateData.objects
        .filter(id__in=Subquery(
            latest_entries.values('id')[:1]
        ))
        .order_by('region')
    )

    regions = [
        {
            'region': r.region,
            'latitude': r.latitude,
            'longitude': r.longitude,
            'yield': r.yield_value,
            'crop': r.crop
        }
        for r in records
    ]

    return render(request, 'data/map.html', {'regions': regions})


def train_models_by_category(request, mode):
    print(mode)
    data = ClimateData.objects.all().values()
    df = pd.DataFrame(data)

    if df.empty or mode not in ['region', 'crop']:
        return render(request, 'data/ml.html', {'error': 'Insufficient or invalid data'})

    models_info = []
    for value in df[mode].unique():
        subset = df[df[mode] == value]

        if len(subset) < 10:
            continue  # замало даних для моделі

        X = subset[['temperature', 'rainfall', 'uv_index', 'soil_quality']]
        y = subset['yield_value']

        model = LinearRegression()
        model.fit(X, y)

        prediction = model.predict(X)
        score = r2_score(y, prediction)

        models_info.append({
            mode: value,
            'sample_size': len(subset),
            'r2_score': round(score, 3),
            'coefficients': dict(zip(X.columns, model.coef_))
        })

    return render(request, 'data/ml.html', {
        'mode': mode,
        'models': models_info
    })


def predict_yield_by_region(request):
    data = ClimateData.objects.all().values()
    df = pd.DataFrame(data)

    if df.empty:
        return render(request, 'data/predict.html', {'error': 'No data available'})

    regions = sorted(df['region'].unique())
    result = None
    input_values = {}

    if request.method == 'POST':
        region = request.POST.get('region')
        try:
            t = float(request.POST.get('temperature'))
            r = float(request.POST.get('rainfall'))
            u = float(request.POST.get('uv_index'))
            s = float(request.POST.get('soil_quality'))
        except (TypeError, ValueError):
            return render(request, 'data/predict.html', {
                'regions': regions,
                'error': 'Invalid input: all fields must be numeric.'
            })

        subset = df[df['region'] == region]
        if len(subset) >= 10:
            X = subset[['temperature', 'rainfall', 'uv_index', 'soil_quality']]
            y = subset['yield_value']
            model = LinearRegression()
            model.fit(X, y)

            # ✅ правильне передбачення з іменами колонок
            input_df = pd.DataFrame([[t, r, u, s]], columns=X.columns)
            predicted = model.predict(input_df)[0]

            result = round(predicted, 2)
            input_values = {
                'region': region,
                'temperature': t,
                'rainfall': r,
                'uv_index': u,
                'soil_quality': s
            }
        else:
            return render(request, 'data/predict.html', {
                'regions': regions,
                'error': f'Not enough data for region: {region}'
            })

        print(result)

    return render(request, 'data/predict.html', {
        'regions': regions,
        'result': result,
        'input_values': input_values
    })

