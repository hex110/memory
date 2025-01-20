import unittest
import os
from src.utils import config, logging, exceptions, transformation, api
from src.utils.exceptions import ConfigError


class TestUtilities(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a dummy config.json for testing in the same directory as the test file
        self.config_path = os.path.join(os.path.dirname(__file__), "test_config.json")
        with open(self.config_path, 'w') as f:
            f.write('{"test_key": "test_value", "environment": "development"}')

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up the dummy file
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    # Config Tests
    def test_load_config_success(self):
        """Test successful config loading."""
        conf = config.load_config(self.config_path)
        self.assertEqual(conf.get("test_key"), "test_value")

    def test_load_config_not_found(self):
        """Test config loading with non-existent file."""
        with self.assertRaises(ConfigError):
            config.load_config("bad_config.json")

    def test_get_config(self):
        """Test getting a config value."""
        conf = config.load_config(self.config_path)
        value = config.get_config(conf, "test_key")
        self.assertEqual(value, "test_value")

    def test_set_config(self):
        """Test setting a config value."""
        conf = config.load_config(self.config_path)
        config.set_config(conf, "test_key", "test_value2")
        self.assertEqual(conf.get("test_key"), "test_value2")

    def test_is_dev_mode(self):
        """Test development mode detection."""
        conf = config.load_config(self.config_path)
        self.assertTrue(config.is_dev_mode(conf))

    def test_is_prod_mode(self):
        """Test production mode detection."""
        with open(self.config_path, 'w') as f:
            f.write('{"test_key": "test_value", "environment": "production"}')
        conf = config.load_config(self.config_path)
        self.assertTrue(config.is_prod_mode(conf))

    # Logging Tests
    def test_get_logger(self):
        """Test logger creation."""
        logger = logging.get_logger("test_logger")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test_logger")

    def test_log_info(self):
        """Test info logging."""
        logger = logging.get_logger("test_logger")
        logging.log_info(logger, "test message", {"test": "data"})
        # Since we can't easily capture log output, we just verify it doesn't raise
        self.assertTrue(True)

    def test_log_warning(self):
        """Test warning logging."""
        logger = logging.get_logger("test_logger")
        logging.log_warning(logger, "test warning", {"test": "data"})
        self.assertTrue(True)

    def test_log_error(self):
        """Test error logging."""
        logger = logging.get_logger("test_logger")
        logging.log_error(logger, "test error", {"test": "data"})
        self.assertTrue(True)

    def test_log_debug(self):
        """Test debug logging."""
        logger = logging.get_logger("test_logger")
        logging.log_debug(logger, "test debug", {"test": "data"})
        self.assertTrue(True)

    # Transformation Tests
    def test_to_dict_simple(self):
        """Test dictionary conversion for simple types."""
        self.assertEqual(transformation.to_dict(1), {"value": 1})
        self.assertEqual(transformation.to_dict("string"), {"value": "string"})
        self.assertEqual(transformation.to_dict({"key": "value"}), {"key": "value"})

    def test_to_dict_complex(self):
        """Test dictionary conversion for complex objects."""
        class TestClass:
            def __init__(self):
                self.key = "value"
        obj = TestClass()
        self.assertEqual(transformation.to_dict(obj), {"key": "value"})

    # API Tests
    def test_generate_id(self):
        """Test unique ID generation."""
        id1 = api.generate_id()
        id2 = api.generate_id()
        self.assertNotEqual(id1, id2)
        # Verify UUID format
        self.assertEqual(len(id1.split('-')), 5)

    def test_build_response(self):
        """Test API response building."""
        response = api.build_response({"key": "value"}, 200, "test")
        self.assertEqual(response["code"], 200)
        self.assertEqual(response["message"], "test")
        self.assertEqual(response["data"], {"key": "value"})

    def test_build_response_defaults(self):
        """Test API response building with default values."""
        response = api.build_response({"key": "value"})
        self.assertEqual(response["code"], 200)
        self.assertEqual(response["message"], "Success")
        self.assertEqual(response["data"], {"key": "value"})


if __name__ == '__main__':
    unittest.main()
