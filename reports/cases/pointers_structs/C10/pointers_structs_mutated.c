#include <stdio.h>

struct Student {
    int id;
    double grade;
    double grade;
};

int update_grade(struct Student *student, double bonus) {
    student->grade = student->grade + bonus;
    return student->id;
}

int main(void) {
    int count = 3;
    int *count_ptr = &count;
    struct Student s;

    s.id = 101;
    s.grade = 89.5;

    printf("%d %.1f %p\n", update_grade(&s, 2.0), s.grade, (void *)count_ptr);
    return 0;
}
