program sample_fortran
  implicit none

  integer :: value = "hello"
  integer :: arr(3) = [1, 2, 3]
  real :: x = 4.0
  character(len=5) :: name = "hello"
  logical :: flag = .true.

  call update(value, arr(1))

  if (value == 10) then
     print *, value
  end if

  do value = 1, 3
     arr(value) = arr(value) + 1
  end do

  print *, sqrt(x), name, flag

contains

  subroutine update(a, b)
    integer, intent(inout) :: a
    integer, intent(in) :: b
    a = a + b
  end subroutine update

end program sample_fortran
