from math import sqrt
import sys
import time

import pygame
import pygame.gfxdraw
from pygame.locals import *

import usb.core
import usb.util


class USBCar(object):
    VID = 0x0a81
    PID = 0x0702

    FORWARD = 1
    RIGHT = 2
    REVERSE_RIGHT = 4
    REVERSE = 8
    REVERSE_LEFT = 16
    LEFT = 32
    STOP = 0

    READ_TIMEOUT = 250

    def __init__(self):
        self._had_driver = False
        self._dev = usb.core.find(idVendor=USBCar.VID, idProduct=USBCar.PID)

        if self._dev is None:
            raise ValueError("Device not found")

        if self._dev.is_kernel_driver_active(0):
            self._dev.detach_kernel_driver(0)
            self._had_driver = True

        self._dev.set_configuration()

    def release(self):
        usb.util.release_interface(self._dev, 0)
        if self._had_driver:
            self._dev.attach_kernel_driver(0)

    def move(self, direction):
        ret = self._dev.ctrl_transfer(0x21, 0x09, 0x0200, 0, [direction])
        return ret == 1

    def battery_status(self):
        try:
            ret = self._dev.read(0x81, 1, timeout=self.READ_TIMEOUT)
            if ret:
                res = ret.tolist()
                if res[0] == 0x05:
                    return 'charging'
                elif res[0] == 0x85:
                    return 'charged'
            return 'unknown'
        except usb.core.USBError:
            # Assume timeout is the only reason
            return 'out of the garage'


class UI(object):
    WINDOW_SIZE = (240, 180)

    K = 0.8
    W = 10

    INDICATOR_POSITION = 5, 5
    INDICATOR_SIZE = 30, 7

    WHITE = pygame.Color(255, 255, 255)
    RED = pygame.Color(255, 0, 0)
    BLACK = pygame.Color(0, 0, 0)

    UPDATEBATTERY = USEREVENT + 1
    UPDATEBATTERY_PERIOD = 3000

    def __init__(self):
        self._car = USBCar()
        self._battery = None
        self._stopped = True

        pygame.init()

        pygame.display.set_mode(self.WINDOW_SIZE)
        pygame.display.set_caption('USBCar Control')

        self._arrows = []
        self._background = pygame.image.load('background.png')
        self._backplate = pygame.Surface(self.WINDOW_SIZE, 24)
        self._clock = pygame.time.Clock()
        # Returned by display.set_mode() as well
        self._window = pygame.display.get_surface()

        self.generate_arrows(self.K, self.W)
        self.setup_backplate([
            USBCar.FORWARD, USBCar.RIGHT, USBCar.REVERSE_RIGHT,
            USBCar.REVERSE, USBCar.REVERSE_LEFT, USBCar.LEFT
        ])

        self.update_battery()
        pygame.time.set_timer(self.UPDATEBATTERY, self.UPDATEBATTERY_PERIOD)

    def main_loop(self):
        while True:
            bg_width, bg_height = self._background.get_size()
            self._window.fill(self.WHITE)
            self._window.blit(self._background,
                              (self.WINDOW_SIZE[0] / 2 - bg_width / 2,
                               self.WINDOW_SIZE[1] / 2 - bg_height / 2))

            if self._battery is not None:
                self.draw_indicator(self._battery)

            self.draw_arrows()

            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    self._car.release()
                    sys.exit(0)
                if event.type == MOUSEBUTTONDOWN:
                    direction = self.get_direction_at(event.pos)
                    self.move_car(direction)
                if event.type == MOUSEBUTTONUP:
                    if event.button == 1:
                        self.move_car(USBCar.STOP)
                if event.type == MOUSEMOTION:
                    if event.buttons[0]:
                        direction = self.get_direction_at(event.pos)
                        if direction == USBCar.STOP and not self._stopped:
                            self.stop_car()
                if event.type == self.UPDATEBATTERY:
                    self.update_battery()
                # You can implement support for cursor keys here

            pygame.display.update()
            self._clock.tick(30)

    def draw_indicator(self, level):
        x, y = self.INDICATOR_POSITION
        w, h = self.INDICATOR_SIZE
        length = float(level % 101) / 100 * (w - 4)
        pygame.gfxdraw.rectangle(self._window, (x, y, x + w, y + h), self.BLACK)
        pygame.gfxdraw.box(self._window, (x + 2, y + 2, x + int(length), y + h - 4), self.BLACK)

    def draw_arrows(self):
        for arrow in self._arrows:
            x1, y1, x2, y2, x3, y3 = arrow
            pygame.gfxdraw.filled_trigon(self._window,
                                         int(x1), int(y1), int(x2), int(y2), int(x3), int(y3), self.RED)

    def setup_backplate(self, commands):
        self._backplate.fill(Color(USBCar.STOP, 0, 0))
        for (arrow, command) in zip(self._arrows, commands):
            x1, y1, x2, y2, x3, y3 = arrow
            pygame.gfxdraw.filled_trigon(self._backplate,
                                         int(x1), int(y1), int(x2), int(y2), int(x3), int(y3),
                                         Color(command, 0, 0))

    def get_direction_at(self, position):
        return self._backplate.get_at(position).r

    def move_car(self, direction):
        self._stopped = not self._car.move(direction)

    def stop_car(self):
        self._stopped = self._car.move(USBCar.STOP)

    def update_battery(self):
        status = self._car.battery_status()
        if status == 'charging':
            if self._battery is None:
                self._battery = 0
            else:
                self._battery += 10
        elif status == 'charged':
            self._battery = 100
        else:
            self._battery = None

    def generate_arrows(self, k, w):
        x, y = self.WINDOW_SIZE[0] / 2, self.WINDOW_SIZE[1] / 2
        rx, ry = self.WINDOW_SIZE[0] / 2 * k, self.WINDOW_SIZE[1] / 2 * k
        self._arrows = []

        # FORWARD
        x1, y1 = x, y - ry
        x2, y2 = x - w, y - ry + w
        x3, y3 = x + w, y - ry + w
        self._arrows.append((x1, y1, x2, y2, x3, y3))

        # RIGHT
        x1, y1 = x + rx / sqrt(2), y - ry / sqrt(2)
        x2, y2 = x + rx / sqrt(2) - w * sqrt(2), y - ry / sqrt(2)
        x3, y3 = x + rx / sqrt(2), y - ry / sqrt(2) + w * sqrt(2)
        self._arrows.append((x1, y1, x2, y2, x3, y3))

        # REVERSE_RIGHT
        x1, y1 = x + rx / sqrt(2), y + ry / sqrt(2)
        x2, y2 = x + rx / sqrt(2), y + ry / sqrt(2) - w * sqrt(2)
        x3, y3 = x + rx / sqrt(2) - w * sqrt(2), y + ry / sqrt(2)
        self._arrows.append((x1, y1, x2, y2, x3, y3))

        # REVERSE
        x1, y1 = x, y + ry
        x2, y2 = x - w, y + ry - w
        x3, y3 = x + w, y + ry - w
        self._arrows.append((x1, y1, x2, y2, x3, y3))

        # REVERSE_LEFT
        x1, y1 = x - rx / sqrt(2), y + ry / sqrt(2)
        x2, y2 = x - rx / sqrt(2) + w * sqrt(2), y + ry / sqrt(2)
        x3, y3 = x - rx / sqrt(2), y + ry / sqrt(2) - w * sqrt(2)
        self._arrows.append((x1, y1, x2, y2, x3, y3))

        # LEFT
        x1, y1 = x - rx / sqrt(2), y - ry / sqrt(2)
        x2, y2 = x - rx / sqrt(2), y - ry / sqrt(2) + w * sqrt(2)
        x3, y3 = x - rx / sqrt(2) + w * sqrt(2), y - ry / sqrt(2)
        self._arrows.append((x1, y1, x2, y2, x3, y3))


if __name__ == "__main__":
    ui = UI()
    ui.main_loop()
