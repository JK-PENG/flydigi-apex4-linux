# SPDX-License-Identifier: MIT
import ctypes
import os
import socket
import unittest
from unittest import mock

from apex4ds5._ds5 import uhid


class UhidRegressionTests(unittest.TestCase):
    def fake_device(self, fd):
        device = object.__new__(uhid.Device)
        device.fd = fd
        device.feature_reports = {}
        device.trace = None
        device._started = False
        device._open = False
        device._close_count = 0
        return device

    def send_event(self, sock, event):
        sock.sendall(bytes(memoryview(event).cast("B")))

    def test_uhid_output_event_reaches_the_report_parser(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            event = uhid._Event()
            event.type = uhid.UHID_OUTPUT
            event.u.output.rtype = uhid.HID_REPORT_TYPE_OUTPUT
            payload = bytes([0x02, 0x04]) + bytes(62)
            event.u.output.size = len(payload)
            ctypes.memmove(event.u.output.data, payload, len(payload))
            self.send_event(peer, event)
            self.assertEqual(list(device.poll()),
                             [(uhid.HID_REPORT_TYPE_OUTPUT, payload)])
            self.assertEqual(uhid.UHID_OUTPUT, 6)  # formerly UHID_OUTPUT_EV
        finally:
            local.close()
            peer.close()

    def test_control_path_set_report_is_replied_to_and_yielded(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            event = uhid._Event()
            event.type = uhid.UHID_SET_REPORT
            event.u.set_report.id = 42
            event.u.set_report.rtype = uhid.HID_REPORT_TYPE_OUTPUT
            payload = bytes([0x02, 0x08]) + bytes(62)
            event.u.set_report.size = len(payload)
            ctypes.memmove(event.u.set_report.data, payload, len(payload))
            self.send_event(peer, event)
            self.assertEqual(list(device.poll()),
                             [(uhid.HID_REPORT_TYPE_OUTPUT, payload)])
            reply = uhid._Event()
            received = peer.recv(uhid.EVENT_SIZE)
            ctypes.memmove(ctypes.byref(reply), received, len(received))
            self.assertEqual(reply.type, uhid.UHID_SET_REPORT_REPLY)
            self.assertEqual(reply.u.set_report_reply.id, 42)
            self.assertEqual(reply.u.set_report_reply.err, 0)
        finally:
            local.close()
            peer.close()

    def test_close_and_stop_are_observable_for_trigger_reset(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            for event_type in (uhid.UHID_CLOSE, uhid.UHID_STOP):
                event = uhid._Event()
                event.type = event_type
                self.send_event(peer, event)
                list(device.poll())
            self.assertEqual(device.close_count, 2)
        finally:
            local.close()
            peer.close()

    def test_virtual_edge_creation_keeps_expected_identity(self):
        with mock.patch.object(uhid.os, "open", return_value=99), \
                mock.patch.object(uhid.Device, "_write") as write:
            device = uhid.Device("Edge", 0x054C, 0x0DF2, b"\x05\x01")
            create = write.call_args.args[0]
            self.assertEqual(create.type, uhid.UHID_CREATE2)
            self.assertEqual(create.u.create2.vendor, 0x054C)
            self.assertEqual(create.u.create2.product, 0x0DF2)
            self.assertEqual(create.u.create2.rd_size, 2)
            device.fd = None

    def test_trace_includes_full_control_output_and_failed_get(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            messages = []
            device.trace = messages.append
            event = uhid._Event()
            event.type = uhid.UHID_SET_REPORT
            event.u.set_report.id = 77
            event.u.set_report.rnum = 2
            event.u.set_report.rtype = uhid.HID_REPORT_TYPE_OUTPUT
            payload = bytes([2]) + bytes(range(1, 48))
            event.u.set_report.size = len(payload)
            ctypes.memmove(event.u.set_report.data, payload, len(payload))
            self.send_event(peer, event)
            self.assertEqual(list(device.poll()), [(1, payload)])
            peer.recv(uhid.EVENT_SIZE)
            event = uhid._Event()
            event.type = uhid.UHID_GET_REPORT
            event.u.get_report.id = 78
            event.u.get_report.rnum = 3
            event.u.get_report.rtype = uhid.HID_REPORT_TYPE_FEATURE
            self.send_event(peer, event)
            list(device.poll())
            peer.recv(uhid.EVENT_SIZE)
            self.assertTrue(any("SET_REPORT" in m and "len=48" in m
                                and payload.hex(" ") in m for m in messages))
            self.assertTrue(any("GET_REPORT" in m and "rnum=0x03" in m
                                and "err=65535" in m for m in messages))
        finally:
            local.close()
            peer.close()

    def test_trace_logs_feature_length_without_pairing_payload(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            messages = []
            device.trace = messages.append
            payload = bytes([9]) + bytes(range(1, 20))
            device.feature_reports[9] = payload
            event = uhid._Event()
            event.type = uhid.UHID_GET_REPORT
            event.u.get_report.rnum = 9
            event.u.get_report.rtype = uhid.HID_REPORT_TYPE_FEATURE
            self.send_event(peer, event)
            list(device.poll())
            self.assertTrue(any("GET_REPORT" in m and "len=20" in m
                                and "err=0" in m for m in messages))
            self.assertFalse(any(payload.hex(" ") in m for m in messages))
        finally:
            local.close()
            peer.close()

    def test_interrupt_output_trace_includes_left_block_tail(self):
        local, peer = socket.socketpair()
        try:
            device = self.fake_device(local.fileno())
            messages = []
            device.trace = messages.append
            event = uhid._Event()
            event.type = uhid.UHID_OUTPUT
            event.u.output.rtype = uhid.HID_REPORT_TYPE_OUTPUT
            payload = bytes([2, 8]) + bytes(20) + bytes([1, 60, 40]) + bytes(23)
            event.u.output.size = len(payload)
            ctypes.memmove(event.u.output.data, payload, len(payload))
            self.send_event(peer, event)
            self.assertEqual(list(device.poll()), [(1, payload)])
            self.assertEqual(len(messages), 1)
            self.assertIn("OUTPUT rtype=1 len=48", messages[0])
            self.assertIn(payload.hex(" "), messages[0])
        finally:
            local.close()
            peer.close()


if __name__ == "__main__":
    unittest.main()
