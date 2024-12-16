from django.db import models

# Create your models here.
class Branch_Name_Model(models.Model):
    branch_name = models.CharField(max_length=100)
    def __str__(self):
        return self.branch_name
    

class Websites_Model(models.Model):
    website_name = models.CharField(max_length=250)
    def __str__(self):
        return self.website_name