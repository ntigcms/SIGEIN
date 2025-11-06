from django.shortcuts import render
from .models import Equipment, Unit

def equipamentos(request):
    equipments = Equipment.objects.all()
    units = Unit.objects.all()
    return render(request, 'equipment.html', {'equipments': equipments, 'units': units})
