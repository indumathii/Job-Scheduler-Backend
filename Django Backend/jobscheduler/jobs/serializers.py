from rest_framework import serializers
from .models import Job
from django.contrib.auth.models import User



class RegisterSerializer(serializers.ModelSerializer):
    confirmpassword=serializers.CharField(write_only=True)

    class Meta:
        model=User
        fields=['username','email','password','confirmpassword']
        extra_kwargs={
            'password':{'write_only':True}
        }
    def validate(self,data):
        if data['password']!=data['confirmpassword']:
            raise serializers.ValidationError("Passwords do not match")
        return data
    
    def create(self,validated_data):
        password=validated_data.pop('confirmpassword')
        user=User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class JobSerializer(serializers.ModelSerializer):
    #deadline = serializers.DateTimeField(input_formats=["%d-%m-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"])
    class Meta:
        model=Job
        fields='__all__'
        print("serializer hit")