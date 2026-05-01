from django.db import models

class UserProfile(models.Model):
    tin = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)

    # NEW: optional signature upload
    signature = models.ImageField(
        upload_to='signatures/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.tin})"
    
class GeneratedLetter(models.Model):
    profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    file = models.FileField(upload_to="letters/")
    created_at = models.DateTimeField(auto_now_add=True)

class Meta:
    unique_together = ('profile',)
