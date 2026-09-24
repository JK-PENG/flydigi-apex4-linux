/* SPDX-License-Identifier: MIT
 * Windows/Proton HID diagnostic, independently implemented using Windows APIs.
 * Default: enumerate and read this relay's known reports. No serial/path dumps.
 * --write requires a selected relay node; one mild side, one second, then Off.
 * Start the Linux relay with --trigger-dry-run --hid-debug for the first test.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define REPORT_LEN 48

/* Public, sanitized fixture already served by this relay, not a real pad MAC.
 * The Python test pins these bytes to _ds5/ds5_usb.py. Proton 11 can replace
 * the product name with "Wireless Controller"; require this exact readback
 * before accepting that generic name. Never trust generic Sony metadata alone.
 */
static const unsigned char relay_pairing[] = {
    0x09, 0x74, 0xe7, 0xd6, 0x3a, 0x53, 0x35, 0x08, 0x25, 0x00,
    0x1e, 0x00, 0xee, 0x74, 0xd0, 0xbc, 0x00, 0x00, 0x00, 0x00
};

static int relay_target(unsigned vid, unsigned pid, const wchar_t *name, unsigned len)
{
    return vid == 0x054c && len == REPORT_LEN &&
        ((pid == 0x0ce6 && wcscmp(name, L"Apex 4 (DualSense)") == 0) ||
         (pid == 0x0df2 && wcscmp(name, L"Apex 4 (DualSense Edge)") == 0));
}

static int renamed_relay(unsigned vid, unsigned pid, const wchar_t *name, unsigned len,
                         const unsigned char *pairing, unsigned size)
{
    return vid == 0x054c && (pid == 0x0ce6 || pid == 0x0df2) && len == REPORT_LEN &&
        wcscmp(name, L"Wireless Controller") == 0 && pairing && size == sizeof(relay_pairing) &&
        memcmp(pairing, relay_pairing, sizeof(relay_pairing)) == 0;
}

static int packet(unsigned char *out, int left, int effect)
{
    unsigned offset = left ? 22 : 11;
    if ((left != 0 && left != 1) || (effect != 1 && effect != 5)) return 0;
    memset(out, 0, REPORT_LEN);
    out[0] = 2;
    out[1] = left ? 8 : 4;
    out[offset] = (unsigned char)effect;
    if (effect == 1) { out[offset + 1] = 60; out[offset + 2] = 40; }
    return 1;
}

static int write_count_ok(unsigned written, unsigned requested, unsigned report_id)
{
    /* Wine's hidclass WRITE_REPORT completion subtracts the nonzero report-ID
     * byte. Proton 11.0-2c returned 47 while UHID received all 48 bytes. Keep
     * reporting the original count, and never allow more than this one byte.
     */
    return written == requested || (report_id != 0 && requested > 0 && written == requested - 1);
}

#ifdef PROBE_PORTABLE_TEST
#include <assert.h>
int main(void)
{
    unsigned char report[REPORT_LEN];
    unsigned char wrong_pairing[sizeof(relay_pairing)];
    assert(relay_target(0x054c, 0x0ce6, L"Apex 4 (DualSense)", 48));
    assert(relay_target(0x054c, 0x0df2, L"Apex 4 (DualSense Edge)", 48));
    assert(!relay_target(0x054c, 0x0ce6, L"Wireless Controller", 48));
    assert(!relay_target(0x04b4, 0x2412, L"Apex 4 (DualSense)", 48));
    assert(!relay_target(0x054c, 0x0df2, L"Apex 4 (DualSense Edge)", 64));
    assert(!packet(report, 2, 1));
    assert(!packet(report, 0, 0xee));
    assert(write_count_ok(48, 48, 2));
    assert(write_count_ok(47, 48, 2));
    assert(!write_count_ok(46, 48, 2));
    assert(!write_count_ok(0, 48, 2));
    assert(!write_count_ok(47, 48, 0));
    assert(renamed_relay(0x054c, 0x0df2, L"Wireless Controller", 48,
                         relay_pairing, sizeof(relay_pairing)));
    memcpy(wrong_pairing, relay_pairing, sizeof(wrong_pairing));
    wrong_pairing[1] ^= 1;
    assert(!renamed_relay(0x054c, 0x0df2, L"Wireless Controller", 48,
                          wrong_pairing, sizeof(wrong_pairing)));
    assert(!renamed_relay(0x054c, 0x0df2, L"Wireless Controller", 48, NULL, 0));
    assert(!renamed_relay(0x04b4, 0x2412, L"Wireless Controller", 48,
                          relay_pairing, sizeof(relay_pairing)));
    assert(!renamed_relay(0x054c, 0x0df2, L"Wireless Controller", 64,
                          relay_pairing, sizeof(relay_pairing)));
    for (int left = 1; left >= 0; --left) {
        for (int effect = 1; effect <= 5; effect += 4) {
            assert(packet(report, left, effect));
            for (unsigned i = 0; i < REPORT_LEN; ++i) printf("%02x", report[i]);
            puts("");
        }
    }
    for (unsigned i = 0; i < sizeof(relay_pairing); ++i) printf("%02x", relay_pairing[i]);
    puts("");
    return 0;
}
#else
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <hidpi.h>

static HANDLE stop_event;
static HANDLE done_event;

static BOOL WINAPI console_control(DWORD kind)
{
    if (kind == CTRL_C_EVENT || kind == CTRL_BREAK_EVENT || kind == CTRL_CLOSE_EVENT) {
        SetEvent(stop_event);
        if (kind == CTRL_CLOSE_EVENT) WaitForSingleObject(done_event, 2000);
        return TRUE;
    }
    return FALSE;
}

enum operation { GET_FEATURE, GET_INPUT, WRITE_FILE, SET_OUTPUT };
struct request {
    HANDLE handle;
    enum operation operation;
    unsigned char data[128];
    DWORD size, error, written;
    BOOL ok;
    DWORD api_error;
    BOOL api_ok;
};

static DWORD WINAPI call_hid(void *arg)
{
    struct request *r = arg;
    SetLastError(0);
    switch (r->operation) {
    case GET_FEATURE: r->ok = HidD_GetFeature(r->handle, r->data, r->size); break;
    case GET_INPUT: r->ok = HidD_GetInputReport(r->handle, r->data, r->size); break;
    case WRITE_FILE:
        r->ok = WriteFile(r->handle, r->data, r->size, &r->written, NULL);
        break;
    case SET_OUTPUT: r->ok = HidD_SetOutputReport(r->handle, r->data, r->size); break;
    }
    r->api_ok = r->ok;
    r->api_error = r->ok ? 0 : GetLastError();
    r->error = r->api_error;
    if (r->operation == WRITE_FILE && r->ok && !write_count_ok(r->written, r->size, r->data[0])) {
        r->ok = FALSE;
        r->error = ERROR_WRITE_FAULT;
    }
    return 0;
}

/* Bound API calls, including synchronous HidD calls, to keep failures visible.
 * If cancellation itself fails, exit with an explicit unknown-cleanup result.
 * A driver that won't cancel cannot support a guaranteed physical reset.
 */
static int perform(struct request *r, const char *label)
{
    HANDLE thread;
    DWORD timeout = r->operation <= GET_INPUT ? 1500 : 250;
    printf("CALL %s report=0x%02x len=%lu\n", label, r->data[0], (unsigned long)r->size);
    thread = CreateThread(NULL, 0, call_hid, r, 0, NULL);
    if (!thread) { printf("ERROR CreateThread=%lu\n", (unsigned long)GetLastError()); return 0; }
    if (WaitForSingleObject(thread, timeout) != WAIT_OBJECT_0) {
        CancelSynchronousIo(thread);
        if (WaitForSingleObject(thread, 1000) != WAIT_OBJECT_0) {
            puts("ERROR API cancellation failed; reset status UNKNOWN. Stop/reset the relay.");
            ExitProcess(3);
        }
        r->ok = FALSE;
        r->error = ERROR_TIMEOUT;
    }
    CloseHandle(thread);
    if (r->operation == WRITE_FILE)
        printf("WRITEFILE_NATIVE api_ok=%d winerror=%lu reported=%lu requested=%lu\n",
               (int)r->api_ok, (unsigned long)r->api_error,
               (unsigned long)r->written, (unsigned long)r->size);
    printf("RESULT %s ok=%d winerror=%lu\n", label, (int)r->ok, (unsigned long)r->error);
    return r->ok;
}

static int send_effect(HANDLE h, int left, int effect, enum operation method)
{
    struct request r = {0};
    r.handle = h; r.operation = method; r.size = REPORT_LEN;
    if (!packet(r.data, left, effect)) return 0;
    printf("EFFECT %s type=0x%02x\n", left ? "left" : "right", effect);
    return perform(&r, method == WRITE_FILE ? "WriteFile" : "HidD_SetOutputReport");
}

static void read_reports(HANDLE h, unsigned input_len)
{
    static const unsigned reports[][2] = {{0x05, 41}, {0x09, 20}, {0x0b, 42}, {0x20, 64}};
    for (unsigned i = 0; i < sizeof(reports) / sizeof(reports[0]); ++i) {
        struct request r = {0};
        r.handle = h; r.operation = GET_FEATURE; r.data[0] = (unsigned char)reports[i][0];
        r.size = reports[i][1];
        perform(&r, "HidD_GetFeature");
    }
    if (input_len > 0 && input_len <= 128) {
        struct request r = {0};
        r.handle = h; r.operation = GET_INPUT; r.data[0] = 1; r.size = input_len;
        perform(&r, "HidD_GetInputReport");
    }
}

int main(int argc, char **argv)
{
    GUID hid_guid;
    HDEVINFO devices;
    int selected = -1, write_enabled = 0, left = 0, matched = 0, result = 0;
    enum operation method = WRITE_FILE;
    setvbuf(stdout, NULL, _IONBF, 0);
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--write")) write_enabled = 1;
        else if (!strcmp(argv[i], "--device") && i + 1 < argc) {
            char *end;
            long value = strtol(argv[++i], &end, 10);
            if (!*argv[i] || *end || value < 0 || value > 65535) return 2;
            selected = (int)value;
        } else if (!strcmp(argv[i], "--side") && i + 1 < argc) {
            const char *side = argv[++i];
            if (strcmp(side, "left") && strcmp(side, "right")) return 2;
            left = !strcmp(side, "left");
        } else if (!strcmp(argv[i], "--method") && i + 1 < argc) {
            const char *name = argv[++i];
            if (strcmp(name, "writefile") && strcmp(name, "setoutput")) return 2;
            method = !strcmp(name, "writefile") ? WRITE_FILE : SET_OUTPUT;
        } else {
            puts("windows-hid-probe [--device N] [--write --side left|right --method writefile|setoutput]");
            puts("Default is read-only. Writes target only a named Apex 4 virtual DS/Edge, mild then Off.");
            return strcmp(argv[i], "--help") ? 2 : 0;
        }
    }
    if (write_enabled && selected < 0) { puts("--write requires --device N from a read-only run."); return 2; }
    stop_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    done_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!stop_event || !done_event) return 2;
    SetConsoleCtrlHandler(console_control, TRUE);
    HidD_GetHidGuid(&hid_guid);
    devices = SetupDiGetClassDevsW(&hid_guid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (devices == INVALID_HANDLE_VALUE) return 2;
    for (DWORD index = 0; ; ++index) {
        SP_DEVICE_INTERFACE_DATA iface = {0};
        PSP_DEVICE_INTERFACE_DETAIL_DATA_W detail;
        HIDD_ATTRIBUTES attrs = {0};
        HIDP_CAPS caps = {0};
        PHIDP_PREPARSED_DATA preparsed;
        WCHAR name[128] = {0};
        DWORD needed = 0;
        HANDLE h;
        int target;
        if (WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0) break;
        iface.cbSize = sizeof(iface);
        if (!SetupDiEnumDeviceInterfaces(devices, NULL, &hid_guid, index, &iface)) {
            if (GetLastError() != ERROR_NO_MORE_ITEMS) result = 2;
            break;
        }
        if (selected >= 0 && index != (DWORD)selected) continue;
        SetupDiGetDeviceInterfaceDetailW(devices, &iface, NULL, 0, &needed, NULL);
        if (!needed || !(detail = calloc(1, needed))) { result = 2; break; }
        detail->cbSize = sizeof(*detail);
        if (!SetupDiGetDeviceInterfaceDetailW(devices, &iface, detail, needed, NULL, NULL)) {
            free(detail); result = 2; continue;
        }
        /* Metadata handle has no write access, including on unrelated devices. */
        h = CreateFileW(detail->DevicePath, 0, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE) { free(detail); continue; }
        attrs.Size = sizeof(attrs);
        if (!HidD_GetAttributes(h, &attrs)) { CloseHandle(h); free(detail); continue; }
        HidD_GetProductString(h, name, sizeof(name));
        name[127] = 0;
        if (HidD_GetPreparsedData(h, &preparsed)) {
            HidP_GetCaps(preparsed, &caps);
            HidD_FreePreparsedData(preparsed);
        }
        target = relay_target(attrs.VendorID, attrs.ProductID, name, caps.OutputReportByteLength)
                 && caps.UsagePage == 1 && caps.Usage == 5;
        if (!target && attrs.VendorID == 0x054c &&
            (attrs.ProductID == 0x0ce6 || attrs.ProductID == 0x0df2) &&
            caps.UsagePage == 1 && caps.Usage == 5 && caps.OutputReportByteLength == REPORT_LEN &&
            wcscmp(name, L"Wireless Controller") == 0) {
            struct request identity = {0};
            identity.handle = h; identity.operation = GET_FEATURE;
            identity.size = sizeof(relay_pairing); identity.data[0] = 9;
            if (perform(&identity, "relay pairing identity"))
                target = renamed_relay(attrs.VendorID, attrs.ProductID, name,
                                       caps.OutputReportByteLength, identity.data, identity.size);
            printf("PAIRING_TEMPLATE_MATCH=%d\n", target);
        }
        printf("DEVICE %lu vid=%04x pid=%04x version=%04x usage=%04x/%04x input=%u output=%u relay=%d\n",
               (unsigned long)index, attrs.VendorID, attrs.ProductID, attrs.VersionNumber,
               caps.UsagePage, caps.Usage, caps.InputReportByteLength, caps.OutputReportByteLength, target);
        if (attrs.VendorID == 0x054c && (attrs.ProductID == 0x0ce6 || attrs.ProductID == 0x0df2)) {
            char product[512] = {0};
            WideCharToMultiByte(CP_UTF8, 0, name, -1, product, sizeof(product), NULL, NULL);
            for (unsigned i = 0; product[i]; ++i)
                if ((unsigned char)product[i] < 32) product[i] = ' ';
            printf("  product=%s\n", product);
        }
        /* Do not print device paths, serial numbers or feature payloads. */
        CloseHandle(h);
        if (!target) {
            if (selected >= 0) { puts("REFUSED: selected node is not this relay's virtual gamepad."); result = 2; }
            free(detail); continue;
        }
        matched++;
        h = CreateFileW(detail->DevicePath, GENERIC_READ | (write_enabled ? GENERIC_WRITE : 0),
                        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
        free(detail);
        if (h == INVALID_HANDLE_VALUE) { printf("ERROR open=%lu\n", (unsigned long)GetLastError()); result = 2; continue; }
        if (!write_enabled) read_reports(h, caps.InputReportByteLength);
        else {
            ULONGLONG start;
            int applied, cleared;
            puts("READY: selected virtual output test; use a dry-run relay first.");
            start = GetTickCount64();
            applied = send_effect(h, left, 1, method);
            if (applied) {
                ULONGLONG elapsed = GetTickCount64() - start;
                if (elapsed < 1000) WaitForSingleObject(stop_event, (DWORD)(1000 - elapsed));
            }
            cleared = send_effect(h, left, 5, method);
            /* Try the other supported route for cleanup if the tested route failed. */
            if (!cleared) cleared = send_effect(h, left, 5, method == WRITE_FILE ? SET_OUTPUT : WRITE_FILE);
            printf("WRITE_TEST applied=%d off=%d (API success requires matching relay log)\n", applied, cleared);
            if (!applied || !cleared) result = 1;
        }
        CloseHandle(h);
    }
    SetupDiDestroyDeviceInfoList(devices);
    if (!matched) { puts("No matching relay virtual controller found."); result = 1; }
    SetEvent(done_event);
    SetConsoleCtrlHandler(console_control, FALSE);
    CloseHandle(stop_event); CloseHandle(done_event);
    return result;
}
#endif
