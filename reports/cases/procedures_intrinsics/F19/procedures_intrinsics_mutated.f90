program procedures_intrinsics
  implicit none

  real :: x = 16.0
  integer :: answer = 0

  call set_answer(answer, 42)

  if (answer == 42) then
     print *, sqrt(x), answer
  end if


  subroutine set_answer(target, value)
    integer, intent(inout) :: target
    integer, intent(in) :: value
    target = value
  end subroutine set_answer

end program procedures_intrinsics
