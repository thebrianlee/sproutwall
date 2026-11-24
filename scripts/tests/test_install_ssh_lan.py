"""install.sh over SSH: which IPv4 address the laptop is given.

The session's own interface decides it, never the default route (a second
uplink such as a USB tether can carry that), and link-local 169.254/16 counts
as the home network in preflight, the same as for the session itself.
"""

import os
import shutil

from . import test_install_sh as base

WLAN_AND_TETHER = (
    "2: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global dynamic wlan0\\\\       valid_lft 86000sec preferred_lft 86000sec\n"
    "5: usb0    inet 10.42.0.2/24 brd 10.42.0.255 scope global dynamic usb0\\\\       valid_lft 3000sec preferred_lft 3000sec"
)
TETHER_ROUTE = "1.1.1.1 via 10.42.0.1 dev usb0 src 10.42.0.2 uid 1000"


CABLE_AND_WIFI = "3: eth0    inet 169.254.10.5/16 brd 169.254.255.255 scope link eth0\\       valid_lft forever preferred_lft forever\n2: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global dynamic wlan0\\       valid_lft 86000sec preferred_lft 86000sec"


class LaptopAddressOverSshTests(base.InstallShTestCase):
    def setUp(self):
        super().setUp()
        self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config"), base.STOCK_SSHD_CONFIG)
        self.write(
            os.path.join(self.sysroot, "etc/ssh/sshd_config.d/50-cloud-init.conf"), "PasswordAuthentication yes\n"
        )

    def fresh(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        shutil.rmtree(self.home)
        os.mkdir(self.home)
        for name in os.listdir(self.state):
            if name.endswith(".count"):
                os.remove(os.path.join(self.state, name))

    def household(self, run):
        return run.out[run.out.index("Set up your household now") : run.out.index("You see")]

    def assert_household_url(self, url, **env):
        run = self.run_install(base.SSH_ANSWERS, **env)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn(url, self.household(run))
        self.assertNotIn("10.42.0.2", self.household(run))
        return run

    def assert_no_laptop_address(self, **env):
        run = self.run_install(base.SSH_ANSWERS, **env)
        self.assert_stopped_before_changes(run)
        self.assertIn("no IPv4 home-network address that your laptop reaches", run.err)

    def test_ipv6_session_uses_its_own_interface_not_the_tether_route(self):
        # The default IPv4 route leaves through a USB tether (usb0); the laptop
        # came in over home Wi-Fi IPv6 (wlan0).
        self.assert_household_url(
            "http://192.168.1.20:3847",
            SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
            FAKE_HOSTNAME="10.42.0.2 192.168.1.20 fd12:3456::50",
            FAKE_IP4=WLAN_AND_TETHER,
            FAKE_ROUTE=TETHER_ROUTE,
        )

    def test_ipv6_session_address_is_matched_whatever_its_letter_case(self):
        self.assert_household_url(
            "http://192.168.1.20:3847",
            SSH_CONNECTION="FD12:3456::7 52344 FD12:3456::50 22",
            FAKE_HOSTNAME="10.42.0.2 192.168.1.20 fd12:3456::50",
            FAKE_IP4=WLAN_AND_TETHER,
            FAKE_ROUTE=TETHER_ROUTE,
        )

    def test_link_local_session_uses_its_interface(self):
        for label, connection in (
            ("with its zone", "fe80::1c2b%wlan0 52344 fe80::50%wlan0 22"),
            ("without a zone", "fe80::1c2b 52344 fe80::50 22"),
        ):
            with self.subTest(label=label):
                self.fresh()
                self.assert_household_url(
                    "http://192.168.1.20:3847",
                    SSH_CONNECTION=connection,
                    FAKE_HOSTNAME="10.42.0.2 192.168.1.20 fd12:3456::50",
                    FAKE_IP4=WLAN_AND_TETHER,
                    FAKE_ROUTE=TETHER_ROUTE,
                )

    def test_ssh_client_only_uses_the_route_to_the_laptop(self):
        self.assert_household_url(
            "http://192.168.1.20:3847",
            SSH_CLIENT="fd12:3456::7 52344 22",
            FAKE_HOSTNAME="10.42.0.2 192.168.1.20 fd12:3456::50",
            FAKE_IP4=WLAN_AND_TETHER,
            FAKE_ROUTE="fd12:3456::7 from :: dev wlan0 proto kernel src fd12:3456::50 metric 256 pref medium",
        )

    def test_container_or_bridge_interface_stops_in_preflight(self):
        cases = {
            "route to the laptop on docker0": dict(
                SSH_CLIENT="fd12:3456::7 52344 22",
                FAKE_ROUTE="fd12:3456::7 from :: dev docker0 proto kernel src fd12:3456::50 metric 256 pref medium",
            ),
            "session address on a bridge": dict(
                SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
                FAKE_IP6_ALL="6: br-3f2a    inet6 fd12:3456::50/64 scope global \\\\       valid_lft forever preferred_lft forever",
            ),
        }
        for label, env in cases.items():
            with self.subTest(label=label):
                self.fresh()
                self.assert_no_laptop_address(**env)

    def test_session_interface_without_a_home_ipv4_stops_in_preflight(self):
        self.assert_no_laptop_address(
            SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
            FAKE_IP4="5: usb0    inet 10.42.0.2/24 brd 10.42.0.255 scope global dynamic usb0",
            FAKE_ROUTE=TETHER_ROUTE,
        )

    def test_unknown_session_address_and_no_route_stops_in_preflight(self):
        self.assert_no_laptop_address(
            SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::99 22",
            FAKE_ROUTE_FAIL="1",
        )

    def test_direct_cable_link_local_ipv4_is_the_home_network(self):
        # A laptop on a direct Ethernet cable at 169.254.x.x while the device
        # uses Wi-Fi for the internet.
        run = self.assert_household_url(
            "http://169.254.10.5:3847",
            SSH_CONNECTION="169.254.10.9 52344 169.254.10.5 22",
            FAKE_HOSTNAME="169.254.10.5 192.168.1.20",
            FAKE_IP4=CABLE_AND_WIFI,
        )
        self.assertNotIn("outside the home-network ranges", run.err)
        # The phone on the Wi-Fi cannot reach the cable's link-local address:
        # the phone check names the device's Wi-Fi address instead.
        self.assertIn("on a phone on the same Wi-Fi, open http://192.168.1.20:3847", run.out)
        self.assertIn("must still show \"Unlock this screen\" at http://192.168.1.20:3847", run.out)
        self.assertNotIn("open http://169.254.10.5:3847. It must show", run.out)

    def test_public_ipv4_next_to_link_local_still_stops(self):
        run = self.run_install(
            base.SSH_ANSWERS,
            SSH_CONNECTION="169.254.10.9 52344 169.254.10.5 22",
            FAKE_HOSTNAME="169.254.10.5 203.0.113.7",
        )
        self.assert_stopped_before_changes(run)
        self.assertIn("outside the home-network ranges", run.err)
        self.assertIn("169.254.", run.err)


class PhoneCheckOnACableTests(base.InstallShTestCase):
    def setUp(self):
        super().setUp()
        # The same SSH settings files as the laptop-address tests.
        self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config"), base.STOCK_SSHD_CONFIG)
        self.write(
            os.path.join(self.sysroot, "etc/ssh/sshd_config.d/50-cloud-init.conf"), "PasswordAuthentication yes\n"
        )

    def test_phone_check_skips_docker_and_says_when_no_phone_can_reach(self):
        # Only the cable and Docker's own network: no phone can reach either.
        run = self.run_install(
            base.SSH_ANSWERS,
            SSH_CONNECTION="169.254.10.9 52344 169.254.10.5 22",
            FAKE_HOSTNAME="169.254.10.5 172.17.0.1",
            FAKE_IP4="3: eth0    inet 169.254.10.5/16 brd 169.254.255.255 scope link eth0\\       valid_lft forever preferred_lft forever\n4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever",
        )
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("http://172.17.0.1:3847", run.out)
        self.assertIn("no phone can", run.out)
        self.assertIn("never one that starts with 169.254. (the cable to your laptop)", run.out)

    def test_laptop_sharing_its_internet_gives_the_phone_the_wifi_address(self):
        # The laptop shares its internet over a cable (NetworkManager shared, 10.42.0.x);
        # the device is also on the home Wi-Fi, where the phone is.
        self.assert_shared_cable_phone_url("10.42.0.1", "10.42.0.23")

    def test_windows_internet_sharing_gives_the_phone_the_wifi_address(self):
        self.assert_shared_cable_phone_url("192.168.137.1", "192.168.137.23")

    def assert_shared_cable_phone_url(self, laptop, device):
        run = self.run_install(
            base.SSH_ANSWERS,
            SSH_CONNECTION="%s 52344 %s 22" % (laptop, device),
            FAKE_HOSTNAME="%s 192.168.1.20" % device,
            FAKE_IP4="3: eth0    inet %s/24 brd 10.42.0.255 scope global dynamic eth0\\       valid_lft forever preferred_lft forever\n2: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global dynamic wlan0\\       valid_lft 86000sec preferred_lft 86000sec" % device,
        )
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("on this computer (the one you are typing on) go to http://%s:3847" % device, run.out)
        self.assertIn("on a phone on the same Wi-Fi, open http://192.168.1.20:3847", run.out)

    def test_laptop_sharing_its_internet_with_no_other_address_keeps_the_laptop_url(self):
        run = self.run_install(
            base.SSH_ANSWERS,
            SSH_CONNECTION="10.42.0.1 52344 10.42.0.23 22",
            FAKE_HOSTNAME="10.42.0.23",
            FAKE_IP4="3: eth0    inet 10.42.0.23/24 brd 10.42.0.255 scope global dynamic eth0\\       valid_lft forever preferred_lft forever",
        )
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("on a phone on the same Wi-Fi, open http://10.42.0.23:3847", run.out)
        self.assertIn("only address is on the cable your laptop shares its internet over", run.out)


class LinkLocalWithoutSshTests(base.InstallShTestCase):
    def test_link_local_ipv4_passes_the_home_network_check(self):
        run = self.run_install(["", "n"], FAKE_HOSTNAME="169.254.3.4 192.168.1.50")
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("outside the home-network ranges", run.err)
        self.assertIn("You did not approve the plan", run.out)
