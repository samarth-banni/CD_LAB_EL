module math_helpers
  implicit none
contains
  subroutine scale_value(value, factor)
    integer, intent(inout) :: value
    integer, intent(in) :: factor
    value = value * factor
  end subroutine scale_value
end module math_helpers

program modules_kinds
  use math_helpers
  implicit none

  integer :: i = 0
  integer :: total = 0
  integer :: values(3) = [2, 4, 6]
  real :: root = 9.0
  character(len=8) :: label = "module"

  do i = 1, 3
     total = total + values(i)
  end do

  call scale_value(total, 2)

  if (total == 24) then
     print *, label, sqrt(root), total
  end if

end program modules_kinds
