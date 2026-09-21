import unittest

from stock_monitor.core.config.container import DIContainer


# Sample classes for testing
class Database:
    pass


class Service:
    def __init__(self, db: Database):
        self.db = db


class Controller:
    def __init__(self, service: Service):
        self.service = service


class TestDIContainer(unittest.TestCase):
    def setUp(self):
        self.container = DIContainer()
        self.container.clear()  # Ensure clean state

    def test_singleton_registration(self):
        """Test registering and retrieving singletons"""
        db = Database()
        self.container.register(Database, db)

        retrieved = self.container.get(Database)
        self.assertIs(retrieved, db)

        # Test string key
        self.container.register("my_db", db)
        self.assertIs(self.container.get("my_db"), db)

    def test_factory_registration(self):
        """Test factory registration - factory creates instance on first get, cached as singleton"""
        factory_calls = []

        def tracking_factory():
            instance = Database()
            factory_calls.append(instance)
            return instance

        self.container.register_factory(Database, tracking_factory)

        # First call should invoke the factory
        result1 = self.container.get(Database)
        self.assertEqual(len(factory_calls), 1)
        self.assertIsInstance(result1, Database)

        # Second call should return the same cached instance (factory NOT called again)
        result2 = self.container.get(Database)
        self.assertEqual(len(factory_calls), 1)  # factory still called only once
        self.assertIs(result1, result2)  # same cached singleton

    def test_automatic_resolution(self):
        """Test automatic dependency resolution"""
        # Register dependency
        db = Database()
        self.container.register(Database, db)

        # Resolve Service which needs Database
        service = self.container.resolve(Service)
        self.assertIsInstance(service, Service)
        self.assertIs(service.db, db)

        # Resolve Controller which needs Service (not registered, but resolvable if Service is resolvable?)
        # Current implementation might not support recursive auto-resolution if Service not registered?
        # Let's test registering Service then resolving Controller
        self.container.register(Service, service)
        controller = self.container.resolve(Controller)
        self.assertIsInstance(controller, Controller)
        self.assertIs(controller.service, service)

    def test_get_with_auto_creation(self):
        """Test backward compatibility auto-creation for known types in _AUTO_CREATEABLE_TYPES"""
        from stock_monitor.config.manager import ConfigManager

        # Ensure ConfigManager is not pre-registered
        self.assertFalse(self.container.has(ConfigManager))

        # get() should auto-create a ConfigManager instance (with DeprecationWarning)
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            instance = self.container.get(ConfigManager)

        self.assertIsInstance(instance, ConfigManager)

        # Should be cached as singleton on second call
        instance2 = self.container.get(ConfigManager)
        self.assertIs(instance, instance2)

    def test_get_unregistered_non_auto_type_raises(self):
        """Test that get() raises KeyError for unregistered types not in _AUTO_CREATEABLE_TYPES"""
        with self.assertRaises(KeyError):
            self.container.get(Controller)


if __name__ == "__main__":
    unittest.main()
