from django.db import models


class ClimateData(models.Model):
    year = models.IntegerField()
    month = models.IntegerField(help_text='Month number (1–12)')
    region = models.CharField(max_length=100)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    crop = models.CharField(max_length=100)
    temperature = models.FloatField()
    rainfall = models.FloatField()
    uv_index = models.FloatField(help_text='UV radiation level')
    soil_quality = models.FloatField(help_text='Soil quality index (0–1)')
    yield_value = models.FloatField(help_text='Crop yield')

    def __str__(self):
        return f"{self.year}-{self.month:02d} | {self.region} | {self.crop}"
