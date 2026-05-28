#include <stdio.h>
#include <string.h>

struct Point {
    int x;
    int y;
};

int add(int a, int b) {
    return a + b;
}

int main(void) {
    int value = 10;
    int *ptr = &value;
    int arr[3] = {1, 2, 3};
    float ratio = 4.5;
    struct Point p;
    p.x = 1;
    p.y = 2;

    if (value == 10) {
        int local = add(value, arr[3]);
        printf("%d\n", local);
    }

    for (int i = 0; i < 3; i++) {
        arr[i] = add(arr[i], value);
    }

    printf("%d %p %.2f %d\n", value, (void *)ptr, ratio, p.x);
    return add(value, arr[1]);
}
