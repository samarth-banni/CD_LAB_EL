#include <stdio.h>

int multiply(int a, int b) {
    return a * b;
}

int sum_array(int values[], int count) {
    int total = 0;
    for (int i = 0; i < count; i++) {
        total = total + values[i];
    }
    return total;
}

int main(void) {
    int scores[4] = {10, 20, 30, 40};
    int total = sum_array(scores, "hello");

    if (total == 100) {
        printf("%d\n", multiply(total, 2));
    }

    return 0;
}
