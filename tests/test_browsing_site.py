import os
import unittest
from selenium import webdriver


class TestCesiSearch(unittest.TestCase):

    def setUp(self):
        # you need to download the driver for the tests from
        # https://github.com/mozilla/geckodriver/releases
        # drivers for other browsers are located here
        # https://selenium-python.readthedocs.io/installation.html#drivers
        self.driver = webdriver.Firefox(executable_path=os.path.abspath('geckodriver'))

    def test_main_page_shows(self):
        driver = self.driver
        driver.get("http://localhost:8000")
        self.assertIn("OEP", driver.title)

    def tearDown(self):
        self.driver.close()


if __name__ == '__main__':
    unittest.main()