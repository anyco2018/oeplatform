from django.db import models
from django.urls import reverse

from markdownx.models import MarkdownxField

# add options if needed
CATEGORY_OPTIONS = [('io', 'I/O'), ('intro', 'Introduction')]
LEVEL_OPTIONS = [(1, '1'), (2, '2'), (3, '3')]

# Create your models here.

class Tutorial(models.Model):
    # ToDo: Fields that are out-commented are missing according to the mockup -> datamodel ??

    category = models.CharField(max_length=15, choices=CATEGORY_OPTIONS, blank=True)
    title = models.TextField()
    html = models.TextField()
    markdown = MarkdownxField()
    level = models.IntegerField(choices=LEVEL_OPTIONS, null=True)

    def get_absolute_url (self):
        return reverse('detail_tutorial', args=[self.id])