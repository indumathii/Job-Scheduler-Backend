import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
 

@pytest.mark.django_db
def test_register_view_success():
    from .serializers import RegisterSerializer 
    from .models import User 
    client = APIClient()
    url = reverse('user-register')  

    # Valid data for registration
    data = {
        'username': 'london',
        'email': 'london@gmail.com',
        'password': 'london123',
        'confirmpassword': 'london123',  
    }
    response = client.post(url, data, format='json')

    assert response.status_code == status.HTTP_201_CREATED

    assert response.data['message'] == 'User registered successfully.'

    user= User.objects.filter(username='london')
    print("Created user Successfully",user)

@pytest.mark.django_db
def test_register_view_failure():
    from .serializers import RegisterSerializer 
    from .models import User 
    client = APIClient()
    url = reverse('user-register') 

    data = {
        'username': '',
        'email': 'test',
        'password': 'short',
        'confirmpassword': 'short2',
    }
   
    response = client.post(url, data, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert 'username' in response.data
    assert 'email' in response.data
    assert 'password' in response.data