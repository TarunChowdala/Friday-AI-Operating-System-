import unittest
from unittest.mock import patch
from app.tools.camera import camera_control


class CameraControlTests(unittest.TestCase):
    @patch("app.tools.camera._camera_pids")
    def test_camera_close_does_not_ask_for_permission(self, mock_pids):
        # Simulate camera running with PID 9999
        mock_pids.return_value = [(9999, "snapshot")]
        with patch("psutil.Process"):
            res = camera_control.invoke({"action": "close"})
            self.assertNotIn("NEEDS_PERMISSION", res)
            self.assertIn("OK:closed camera", res)

    @patch("app.tools.camera._camera_pids")
    def test_camera_photo_blocks_if_camera_app_running(self, mock_pids):
        mock_pids.return_value = [(9999, "snapshot")]
        res = camera_control.invoke({"action": "photo"})
        self.assertIn("The camera app is currently open", res)
        self.assertNotIn("ioctl", res)


if __name__ == "__main__":
    unittest.main()
