from django.http import HttpResponse

def home(request):
    return HttpResponse("MeetIN backend is running")
